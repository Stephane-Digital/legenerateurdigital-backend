from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.token_service import (
    get_valid_activation_token,
    mark_activation_token_used,
)

router = APIRouter(prefix="/auth", tags=["Auth Activation"])


class ConsumeTokenPayload(BaseModel):
    token: str


@router.get("/activate-token")
def activate_token(token: str, db: Session = Depends(get_db)):
    record = get_valid_activation_token(db, token)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide, expiré ou déjà utilisé.",
        )

    return {
        "email": record.email,
        "access_type": record.access_type,
        "plan": record.plan,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "used": bool(record.used),
    }


@router.post("/consume-token")
def consume_token(payload: ConsumeTokenPayload, db: Session = Depends(get_db)):
    record = get_valid_activation_token(db, payload.token)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide, expiré ou déjà utilisé.",
        )

    used = mark_activation_token_used(db, payload.token)
    if not used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de consommer le token.",
        )

    return {"status": "ok"}
