from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.activation_token import ActivationToken


DEFAULT_TOKEN_HOURS = 24


def generate_activation_token_value() -> str:
    return secrets.token_urlsafe(32)


def get_activation_expiration(hours: int = DEFAULT_TOKEN_HOURS) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)


def create_activation_token(
    db: Session,
    *,
    email: str,
    access_type: Optional[str] = None,
    plan: Optional[str] = None,
    expires_in_hours: int = DEFAULT_TOKEN_HOURS,
) -> ActivationToken:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email is required")

    token_value = generate_activation_token_value()
    token = ActivationToken(
        email=email,
        token=token_value,
        access_type=access_type,
        plan=plan,
        expires_at=get_activation_expiration(expires_in_hours),
        used=False,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_valid_activation_token(db: Session, token_value: str) -> Optional[ActivationToken]:
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
