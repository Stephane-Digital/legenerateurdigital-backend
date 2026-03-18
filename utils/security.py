from fastapi import Depends, HTTPException, Request, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from database import get_db
from config.settings import settings
from models.user_model import User


def create_access_token(*args, **kwargs):
    """
    Compatibilité défensive :
    si un ancien import pointe encore vers security.create_access_token,
    on redirige vers la vraie implémentation dans services.auth_service.
    """
    from services.auth_service import create_access_token as _create_access_token
    return _create_access_token(*args, **kwargs)


def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")

        if user_id is None:
            return None

        return int(user_id)

    except JWTError:
        return None
    except Exception:
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Auth LGD unifiée :
    1) Cookie lgd_token
    2) Fallback Bearer token
    """
    token = request.cookies.get("lgd_token")

    if not token:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
