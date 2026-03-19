from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config.settings import settings
from database import get_db
from models.user_model import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# 🔐 HASH / VERIFY
# ============================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# 🔐 CRÉATION TOKEN
# ============================================================

def create_access_token(data: dict, expires_minutes: Optional[int] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


# ============================================================
# 👤 VERSION LGD : get_current_user
# ============================================================

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Version LGD — priorité au cookie `lgd_token`,
    avec fallback Bearer pour compatibilité outils / Swagger / edge cases.
    """

    token = request.cookies.get("lgd_token")

    if not token:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired"
        )

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


# ============================================================
# 🔍 AUTHENTIFIER L’UTILISATEUR
# ============================================================

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email.lower().strip()).first()

    if not user:
        return False

    # ✅ Source de vérité actuelle
    if user.hashed_password:
        if verify_password(password, user.hashed_password):
            return user
        return False

    # ⚠️ Fallback legacy si ancienne donnée en clair existe encore
    if user.password and user.password == password:
        return user

    return False
