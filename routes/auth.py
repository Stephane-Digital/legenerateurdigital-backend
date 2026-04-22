
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from schemas.user_schema import UserCreate
from services.auth_service import (
    JWT_ALGORITHM,
    JWT_SECRET,
    authenticate_user,
    create_access_token,
    create_user_account,
    get_current_user as service_get_current_user,
)
from services.ai_quota_service import get_or_create_quota
from services.pending_access_service import consume_pending_access, has_pending_access

router = APIRouter(prefix="/auth", tags=["Authentication"])

from services.integrations.systeme_subscription_service import cancel_subscription_for_user


def _limit_for_plan(plan: str) -> int:
    p = str(plan or "").lower()
    if p == "trial":
        return 10_000
    if p == "ultime":
        return 2_500_000
    if p == "pro":
        return 1_000_000
    return 400_000


@router.post("/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    full_name = getattr(payload, "full_name", None)

    pending = consume_pending_access(db, email=email)
    if not pending:
        raise HTTPException(
            status_code=403,
            detail="Accès non activé. Passe d'abord par l’offre d’essai ou d’achat LGD."
        )

    created = create_user_account(
        db=db,
        email=email,
        password=payload.password,
        full_name=full_name or pending.get("full_name"),
    )

    user_id = int(created["id"])
    plan = str(pending.get("plan") or "trial").lower()

    try:
        from sqlalchemy import text
        db.execute(
            text("UPDATE users SET plan = :plan WHERE id = :uid"),
            {"uid": user_id, "plan": plan},
        )
    except Exception:
        print("⚠️ users.plan absent, skip set")

    limit_tokens = _limit_for_plan(plan)

    for feature_name in ("coach", "global"):
        quota = get_or_create_quota(db, user_id, feature=feature_name)
        if hasattr(quota, "tokens_used"):
            quota.tokens_used = 0
        if hasattr(quota, "credits"):
            quota.credits = limit_tokens
        if hasattr(quota, "plan"):
            quota.plan = plan
        db.add(quota)

    db.commit()

    return {
        "message": "Compte activé",
        "user_id": user_id,
        "plan": plan,
        "access_type": pending.get("access_type"),
    }


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        content_type = (request.headers.get("content-type") or "").lower()

        email = None
        password = None

        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        elif "application/json" in content_type:
            body = await request.json()
            email = body.get("email") or body.get("username")
            password = body.get("password")
        else:
            try:
                body = await request.json()
                email = body.get("email") or body.get("username")
                password = body.get("password")
            except Exception:
                form = await request.form()
                email = form.get("username") or form.get("email")
                password = form.get("password")

        email = (email or "").strip().lower()
        password = password or ""

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email ou mot de passe manquant")

        user = authenticate_user(db, email, password)
        if not user:
            raise HTTPException(status_code=401, detail="Identifiants invalides")

        token = create_access_token({"sub": str(user["id"]), "email": user["email"], "user_id": user["id"]})

        response = JSONResponse(
            {
                "message": "Connexion réussie",
                "token": token,
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "plan": user["plan"],
                    "is_active": user["is_active"],
                    "is_admin": user["is_admin"],
                },
            }
        )

        response.set_cookie(
            key="lgd_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=60 * 60 * 24 * 7,
            path="/",
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        print("LOGIN ERROR:", repr(e))
        return JSONResponse(status_code=500, content={"detail": f"LOGIN_ERROR: {repr(e)}"})


@router.post("/logout")
def logout():
    response = JSONResponse({"message": "Déconnexion réussie"})
    response.delete_cookie(key="lgd_token", path="/")
    return response


@router.get("/me")
def me(current_user=Depends(service_get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "plan": current_user["plan"],
        "is_active": current_user["is_active"],
        "is_admin": current_user["is_admin"],
    }


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("lgd_token")
    if not token:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")

    current_user = service_get_current_user.__wrapped__(
        credentials=type("Creds", (), {"credentials": token})(),
        db=db,
    ) if hasattr(service_get_current_user, "__wrapped__") else None

    if current_user is None:
        from services.auth_service import _fetch_user_by_identity
        current_user = _fetch_user_by_identity(db, user_id=user_id, email=email)

    if not current_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return current_user


@router.get("/pending-access")
def pending_access_status(email: str, db: Session = Depends(get_db)):
    clean_email = (email or "").strip().lower()
    if not clean_email:
        raise HTTPException(status_code=400, detail="Email manquant")
    return has_pending_access(db, clean_email)


@router.get("/subscription")
def subscription_status(current_user=Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "plan": current_user["plan"],
        "is_active": current_user["is_active"],
        "is_admin": current_user["is_admin"],
    }


@router.post("/subscription/cancel")
def cancel_subscription(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    body = payload or {}
    cancel_mode = body.get("cancel_mode") or "end_of_period"
    reason = body.get("reason") or None
    return cancel_subscription_for_user(
        db,
        user=current_user,
        cancel_mode=cancel_mode,
        reason=reason,
    )
