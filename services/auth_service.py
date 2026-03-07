from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from database import get_db
from config.settings import settings
from models.user_model import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# 🔐 HASH / VERIFY
# ============================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# 🔐 CRÉATION TOKEN
# ============================================================

def create_access_token(data: dict, expires_minutes: int = None):
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
# 👤 NOUVELLE VERSION : get_current_user
# ============================================================

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Version LGD — 100% COOKIES.
    Cette fonction lit EXCLUSIVEMENT le cookie `lgd_token`.
    """

    token = request.cookies.get("lgd_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (missing cookie)"
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
    user = db.query(User).filter(User.email == email.lower()).first()

    if not user:
        return False

    if not verify_password(password, user.password):
        return False

    return user
