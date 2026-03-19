from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config.settings import settings
from database import get_db
from models.user_model import User
from schemas.user_schema import UserCreate
from services.auth_service import (
    authenticate_user,
    create_access_token,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================
# 🧪 REGISTER
# ============================================================
@router.post("/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    hashed = hash_password(payload.password)

    new_user = User(
        email=email,
        name=payload.full_name,
        full_name=payload.full_name,
        hashed_password=hashed,
        password=None,
        is_active=True,
        is_admin=False,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Compte créé", "user_id": new_user.id}


# ============================================================
# 🔐 LOGIN
# ============================================================
@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
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
            try:
                form = await request.form()
                email = form.get("username") or form.get("email")
                password = form.get("password")
            except Exception:
                pass

    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email ou mot de passe manquant")

    user = authenticate_user(db, email, password)

    if not user:
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = create_access_token({"sub": str(user.id)})

    response = JSONResponse(
        {
            "message": "Connexion réussie",
            "token": token,
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name or user.name,
                "plan": user.plan,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
            },
        }
    )

    response.set_cookie(
        key="lgd_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

    return response


# ============================================================
# 🚪 LOGOUT
# ============================================================
@router.post("/logout")
def logout():
    response = JSONResponse({"message": "Déconnexion réussie"})
    response.delete_cookie(
        key="lgd_token",
        path="/",
    )
    return response


# ============================================================
# 👤 ME
# ============================================================
@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("lgd_token")

    if not token:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")

    from jose import JWTError, jwt

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name or user.name,
        "plan": user.plan,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
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

    from jose import JWTError, jwt

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return user
