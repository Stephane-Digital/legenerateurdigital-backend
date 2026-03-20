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

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================
# 🧪 REGISTER
# ============================================================
@router.post("/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    created = create_user_account(
        db=db,
        email=payload.email,
        password=payload.password,
        full_name=getattr(payload, "full_name", None),
    )
    return {"message": "Compte créé", "user_id": created["id"]}


# ============================================================
# 🔐 LOGIN
# ============================================================
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

        token = create_access_token(
            {
                "sub": str(user["id"]),
                "email": user["email"],
                "user_id": user["id"],
            }
        )

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
        return JSONResponse(
            status_code=500,
            content={"detail": f"LOGIN_ERROR: {repr(e)}"},
        )


# ============================================================
# 🚪 LOGOUT
# ============================================================
@router.post("/logout")
def logout():
    response = JSONResponse({"message": "Déconnexion réussie"})
    response.delete_cookie(key="lgd_token", path="/")
    return response


# ============================================================
# 👤 ME
# ============================================================
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


# ============================================================
# ⭐ get_current_user — Cookie FIRST, Header Bearer fallback
# ============================================================
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

    current_user = service_get_current_user.__wrapped__(  # type: ignore[attr-defined]
        credentials=type("Creds", (), {"credentials": token})(),
        db=db,
    ) if hasattr(service_get_current_user, "__wrapped__") else None

    if current_user is None:
        from services.auth_service import _fetch_user_by_identity
        current_user = _fetch_user_by_identity(db, user_id=user_id, email=email)

    if not current_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return current_user
