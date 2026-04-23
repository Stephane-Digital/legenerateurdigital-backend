from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.activation_token import ActivationToken


DEFAULT_TOKEN_HOURS = 24
DEFAULT_FRONT_URL = "https://legenerateurdigital-front.vercel.app"


def ensure_activation_tokens_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS activation_tokens (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                access_type TEXT NULL,
                plan TEXT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                used_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_activation_tokens_email
            ON activation_tokens (email)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_activation_tokens_token
            ON activation_tokens (token)
            """
        )
    )
    db.commit()


def generate_activation_token_value() -> str:
    return secrets.token_urlsafe(32)


def get_activation_expiration(hours: int = DEFAULT_TOKEN_HOURS) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)


def build_activation_link(token_value: str) -> str:
    base = (os.getenv("LGD_FRONT_URL") or os.getenv("FRONTEND_URL") or DEFAULT_FRONT_URL).strip().rstrip("/")
    return f"{base}/auth/activate?token={token_value}"


def invalidate_previous_tokens(
    db: Session,
    *,
    email: str,
    access_type: Optional[str] = None,
) -> None:
    ensure_activation_tokens_table(db)

    clean_email = (email or "").strip().lower()
    if not clean_email:
        return

    if access_type:
        db.execute(
            text(
                """
                UPDATE activation_tokens
                SET used = TRUE,
                    used_at = NOW()
                WHERE LOWER(email) = LOWER(:email)
                  AND COALESCE(access_type, '') = COALESCE(:access_type, '')
                  AND used = FALSE
                """
            ),
            {
                "email": clean_email,
                "access_type": str(access_type or "").strip().lower(),
            },
        )
    else:
        db.execute(
            text(
                """
                UPDATE activation_tokens
                SET used = TRUE,
                    used_at = NOW()
                WHERE LOWER(email) = LOWER(:email)
                  AND used = FALSE
                """
            ),
            {"email": clean_email},
        )
    db.commit()


def create_activation_token(
    db: Session,
    *,
    email: str,
    access_type: Optional[str] = None,
    plan: Optional[str] = None,
    expires_in_hours: int = DEFAULT_TOKEN_HOURS,
    invalidate_old_tokens: bool = True,
) -> ActivationToken:
    ensure_activation_tokens_table(db)

    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email is required")

    clean_access_type = str(access_type or "").strip().lower() or None
    clean_plan = str(plan or "").strip().lower() or None

    if invalidate_old_tokens:
        invalidate_previous_tokens(db, email=email, access_type=clean_access_type)

    token_value = generate_activation_token_value()
    token = ActivationToken(
        email=email,
        token=token_value,
        access_type=clean_access_type,
        plan=clean_plan,
        expires_at=get_activation_expiration(expires_in_hours),
        used=False,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def create_activation_package(
    db: Session,
    *,
    email: str,
    access_type: Optional[str] = None,
    plan: Optional[str] = None,
    expires_in_hours: int = DEFAULT_TOKEN_HOURS,
    invalidate_old_tokens: bool = True,
) -> dict:
    token = create_activation_token(
        db,
        email=email,
        access_type=access_type,
        plan=plan,
        expires_in_hours=expires_in_hours,
        invalidate_old_tokens=invalidate_old_tokens,
    )
    return {
        "token": token.token,
        "activation_url": build_activation_link(token.token),
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "email": token.email,
        "access_type": token.access_type,
        "plan": token.plan,
    }


def get_valid_activation_token(db: Session, token_value: str) -> Optional[ActivationToken]:
    ensure_activation_tokens_table(db)

    token_value = (token_value or "").strip()
    if not token_value:
        return None

    token = (
        db.query(ActivationToken)
        .filter(ActivationToken.token == token_value)
        .first()
    )
    if not token:
        return None

    if token.used:
        return None

    if token.expires_at < datetime.utcnow():
        return None

    return token


def mark_activation_token_used(db: Session, token_value: str) -> Optional[ActivationToken]:
    ensure_activation_tokens_table(db)

    token = (
        db.query(ActivationToken)
        .filter(ActivationToken.token == (token_value or "").strip())
        .first()
    )
    if not token:
        return None

    token.used = True
    token.used_at = datetime.utcnow()
    db.add(token)
    db.commit()
    db.refresh(token)
    return token
