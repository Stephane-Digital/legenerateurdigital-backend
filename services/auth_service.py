import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models.user_model import User

try:
    from config.settings import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


# ============================================================
# CONFIG
# ============================================================
def _setting(name: str, default: Any = None) -> Any:
    if settings is not None and hasattr(settings, name):
        value = getattr(settings, name)
        if value not in (None, ""):
            return value
    return os.getenv(name, default)


JWT_SECRET = _setting("SECRET_KEY", _setting("JWT_SECRET", "change-me-in-production"))
JWT_ALGORITHM = _setting("ALGORITHM", _setting("JWT_ALGORITHM", "HS256"))
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    _setting("ACCESS_TOKEN_EXPIRE_MINUTES", _setting("JWT_EXPIRE_MINUTES", 60))
)


# ============================================================
# SCHEMA INSPECTION HELPERS
# ============================================================
def _users_columns(db: Session) -> set[str]:
    engine = db.get_bind()
    return {col["name"] for col in inspect(engine).get_columns("users")}


def _first_existing(columns: set[str], *candidates: str) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _build_login_query(columns: set[str]) -> str:
    password_col = _first_existing(
        columns,
        "hashed_password",
        "password_hash",
        "password",
        "hashed_pwd",
    )
    if not password_col:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth schema error: aucun champ mot de passe compatible trouvé dans users.",
        )

    name_col = _first_existing(columns, "name", "full_name", "username")
    plan_col = _first_existing(columns, "plan", "subscription_plan")
    active_col = _first_existing(columns, "is_active", "active", "enabled")
    admin_col = _first_existing(columns, "is_admin", "admin")
    created_col = _first_existing(columns, "created_at")
    updated_col = _first_existing(columns, "updated_at")

    select_parts = [
        "id",
        "email",
        f"{password_col} AS password_hash",
        f"{name_col} AS full_name" if name_col else "NULL AS full_name",
        f"{plan_col} AS plan" if plan_col else "NULL AS plan",
        f"{active_col} AS is_active" if active_col else "TRUE AS is_active",
        f"{admin_col} AS is_admin" if admin_col else "FALSE AS is_admin",
        created_col if created_col else "NULL AS created_at",
        updated_col if updated_col else "NULL AS updated_at",
    ]

    return f"""
        SELECT {", ".join(select_parts)}
        FROM users
        WHERE LOWER(email) = LOWER(:email)
        ORDER BY id DESC
        LIMIT 1
    """


def _build_identity_query(columns: set[str], where_clause: str) -> str:
    name_col = _first_existing(columns, "name", "full_name", "username")
    plan_col = _first_existing(columns, "plan", "subscription_plan")
    active_col = _first_existing(columns, "is_active", "active", "enabled")
    admin_col = _first_existing(columns, "is_admin", "admin")
    created_col = _first_existing(columns, "created_at")
    updated_col = _first_existing(columns, "updated_at")

    select_parts = [
        "id",
        "email",
        f"{name_col} AS full_name" if name_col else "NULL AS full_name",
        f"{plan_col} AS plan" if plan_col else "NULL AS plan",
        f"{active_col} AS is_active" if active_col else "TRUE AS is_active",
        f"{admin_col} AS is_admin" if admin_col else "FALSE AS is_admin",
        created_col if created_col else "NULL AS created_at",
        updated_col if updated_col else "NULL AS updated_at",
    ]

    return f"""
        SELECT {", ".join(select_parts)}
        FROM users
        WHERE {where_clause}
        ORDER BY id DESC
        LIMIT 1
    """


# ============================================================
# PASSWORD / TOKEN HELPERS
# ============================================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ============================================================
# USER SERIALIZATION
# ============================================================
def _row_to_user_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    email_value = str(row.get("email") or "").strip()
    fallback_name = email_value.split("@")[0] if "@" in email_value else "Utilisateur"
    return {
        "id": row.get("id"),
        "email": email_value,
        "full_name": row.get("full_name") or fallback_name,
        "plan": row.get("plan") or "essentiel",
        "is_active": bool(row.get("is_active", True)),
        "is_admin": bool(row.get("is_admin", False)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# ============================================================
# CORE AUTH
# ============================================================
def authenticate_user(db: Session, email: str, password: str) -> Optional[Dict[str, Any]]:
    try:
        columns = _users_columns(db)
        query = _build_login_query(columns)
        row = db.execute(text(query), {"email": email}).mappings().first()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database auth error: {exc.__class__.__name__}",
        ) from exc

    if not row:
        return None

    user = _row_to_user_dict(dict(row))

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé.",
        )

    stored_hash = str(row.get("password_hash") or "").strip()
    if not stored_hash:
        return None

    if not verify_password(password, stored_hash):
        return None

    return user


def login_user(db: Session, email: str, password: str) -> Dict[str, Any]:
    user = authenticate_user(db, email=email, password=password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {
            "sub": str(user["id"]),
            "email": user["email"],
            "user_id": user["id"],
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


def create_user_account(db: Session, email: str, password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email ou mot de passe manquant")

    columns = _users_columns(db)

    existing = db.execute(
        text("SELECT id FROM users WHERE LOWER(email) = LOWER(:email) LIMIT 1"),
        {"email": email},
    ).mappings().first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    user = User()
    if "email" in columns:
        user.email = email
    if "full_name" in columns:
        user.full_name = full_name
    elif hasattr(user, "full_name"):
        user.full_name = full_name

    hashed = hash_password(password)
    if "hashed_password" in columns:
        user.hashed_password = hashed
    elif "password_hash" in columns:
        setattr(user, "password_hash", hashed)
    elif "password" in columns:
        setattr(user, "password", hashed)
    else:
        raise HTTPException(
            status_code=500,
            detail="Auth schema error: aucun champ mot de passe compatible trouvé dans users.",
        )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "full_name": getattr(user, "full_name", None),
    }


# ============================================================
# CURRENT USER
# ============================================================
def _fetch_user_by_identity(db: Session, *, user_id: Any = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    columns = _users_columns(db)

    if "email" not in columns:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth schema error: colonne email introuvable dans users.",
        )

    where_clause = None
    params: Dict[str, Any] = {}

    if user_id is not None and "id" in columns:
        where_clause = "id = :user_id"
        params["user_id"] = user_id
    elif email:
        where_clause = "LOWER(email) = LOWER(:email)"
        params["email"] = email

    if not where_clause:
        return None

    query = _build_identity_query(columns, where_clause)

    try:
        row = db.execute(text(query), params).mappings().first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database auth error: {exc.__class__.__name__}",
        ) from exc

    if not row:
        return None

    return _row_to_user_dict(dict(row))


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email") or payload.get("sub")
        user_id = payload.get("user_id") or payload.get("sub")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = _fetch_user_by_identity(db, user_id=user_id, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
