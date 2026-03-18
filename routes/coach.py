from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user
from models.user_model import User
from services.ai_quota_adapter import consume_tokens, get_user_quota
from services.ai.coach_ai import generate_coach_reply

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachQuotaOut(BaseModel):
    plan: Optional[str] = None
    tokens_total: int
    tokens_used: int
    tokens_remaining: int
    reset_at: Optional[str] = None
    feature: Optional[str] = "coach"
    source: Optional[str] = "ia_quota"


class CoachChatIn(BaseModel):
    message: str
    mode: Optional[str] = "action"
    focus: Optional[str] = None
    context: Optional[dict] = None


class CoachChatOut(BaseModel):
    reply: str


@router.get("/quota", response_model=CoachQuotaOut)
def coach_quota(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = get_user_quota(db, user, feature="coach")
    return CoachQuotaOut(
        plan=q.get("plan"),
        tokens_total=int(q.get("tokens_limit", 0)),
        tokens_used=int(q.get("tokens_used", 0)),
        tokens_remaining=int(q.get("tokens_remaining", 0)),
        reset_at=None,
        feature=q.get("feature", "coach"),
        source=q.get("source", "ia_quota"),
    )


@router.post("/chat", response_model=CoachChatOut)
def coach_chat(
    payload: CoachChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = get_user_quota(db, user, feature="coach")
    if int(q.get("tokens_remaining", 0)) <= 0:
        raise HTTPException(status_code=402, detail="Quota épuisé")

    # Réponse coach (template-based stable)
    reply = generate_coach_reply(
        mode=payload.mode or "action",
        message=payload.message,
        plan=q.get("plan") or "essentiel",
        user_name=getattr(user, "full_name", None) or "Utilisateur",
        depth=2,
    )

    # Consommation tokens (approx. 4 chars ~= 1 token)
    tokens_used = max(int(len(reply) / 4), 1)
    try:
        consume_tokens(db, user, tokens_used, feature="coach")
    except Exception:
        pass

    return CoachChatOut(reply=reply)
