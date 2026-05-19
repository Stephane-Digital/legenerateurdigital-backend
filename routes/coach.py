from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user
from models.user_model import User
from services.ai_quota_adapter import consume_tokens, get_user_quota
from services.ai.coach_ai import generate_coach_reply
from services.coach_profile_service import read_profile

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
    focus: Optional[str] = "jour"
    context: Optional[Dict[str, Any]] = None


class CoachChatOut(BaseModel):
    reply: str


def _merge_context(profile: Dict[str, Any], request_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base: Dict[str, Any] = {}

    if isinstance(profile, dict):
        base.update(profile)
        snap = profile.get("coach_v2")
        if isinstance(snap, dict):
            ctx = snap.get("context")
            if isinstance(ctx, dict):
                base.update(ctx)

    if isinstance(request_context, dict):
        base.update(request_context)

    return base


def _reply_and_usage(result: Dict[str, Any] | str) -> tuple[str, int]:
    if isinstance(result, dict):
        reply = str(result.get("reply") or "").strip()
        usage = result.get("usage") or {}
        try:
            tokens = int(usage.get("total_tokens") or 0)
        except Exception:
            tokens = 0
        return reply, tokens

    reply = str(result or "").strip()
    return reply, 0


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

    profile = read_profile(db, int(getattr(user, "id")))
    merged_context = _merge_context(profile, payload.context)

    result = generate_coach_reply(
        mode=payload.mode or "action",
        focus=payload.focus or "jour",
        message=payload.message,
        plan=q.get("plan") or "essentiel",
        user_name=getattr(user, "full_name", None) or "Utilisateur",
        user_id=int(getattr(user, "id")),
        user_email=getattr(user, "email", None),
        context=merged_context,
    )

    reply, real_tokens = _reply_and_usage(result)
    if not reply:
        reply = "Je suis Alex. Donne-moi ton objectif, ton temps disponible et ton blocage principal. Je te donne une prochaine action claire."

    tokens_used = real_tokens if real_tokens > 0 else max(int((len(payload.message or "") + len(reply)) / 4), 1)
    try:
        consume_tokens(db, user, tokens_used, feature="coach")
    except Exception:
        pass

    return CoachChatOut(reply=reply)
