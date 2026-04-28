from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.cmo_ai import generate_cmo_strategy
from services.ai_quota_service import update_quota

router = APIRouter(prefix="/cmo-ai", tags=["CMO IA V5"])


class CmoStrategyRequest(BaseModel):
    objective: str
    niche: Optional[str] = None
    audience: Optional[str] = None
    offer: Optional[str] = None
    current_situation: Optional[str] = None
    constraints: Optional[str] = None
    preferred_channel: Optional[str] = None
    tone: Optional[str] = "premium, humain, direct"
    user_level: Optional[str] = "intermediate"


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _estimate_tokens(payload: CmoStrategyRequest) -> int:
    text = " ".join(
        [
            str(payload.objective or ""),
            str(payload.niche or ""),
            str(payload.audience or ""),
            str(payload.offer or ""),
            str(payload.current_situation or ""),
            str(payload.constraints or ""),
            str(payload.preferred_channel or ""),
            str(payload.tone or ""),
            str(payload.user_level or ""),
        ]
    )
    return max(1800, min(int(len(text) / 3) + 2200, 15000))


@router.post("/strategy")
def cmo_strategy(
    payload: CmoStrategyRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    uid = _user_id(current_user)
    amount = _estimate_tokens(payload)

    quota = update_quota(db, uid, amount, feature="coach")
    if quota is None:
        raise HTTPException(status_code=400, detail="Quota IA insuffisant.")

    try:
        result = generate_cmo_strategy(
            objective=payload.objective,
            niche=payload.niche or "",
            audience=payload.audience or "",
            offer=payload.offer or "",
            current_situation=payload.current_situation or "",
            constraints=payload.constraints or "",
            preferred_channel=payload.preferred_channel or "",
            tone=payload.tone or "premium, humain, direct",
            user_level=payload.user_level or "intermediate",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "success": True,
        "tokens_charged": amount,
        "result": result,
    }


@router.get("/health")
def cmo_health():
    return {
        "status": "ok",
        "module": "CMO IA V5",
        "mode": "next_best_action",
    }
