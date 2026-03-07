from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.coach_ai import generate_coach_reply
from services.ai_quota_service import get_or_create_quota, update_quota

router = APIRouter(prefix="/coach", tags=["Coach IA"])


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def _quota_snapshot(q: Any) -> Dict[str, int]:
    # Align with services.ai_quota_service model compatibility
    used = _to_int(getattr(q, "tokens_used", None), 0)
    if used == 0 and getattr(q, "used_tokens", None) is not None:
        used = _to_int(getattr(q, "used_tokens", None), 0)

    limit = _to_int(getattr(q, "credits", None), 0)
    if limit == 0 and getattr(q, "tokens_limit", None) is not None:
        limit = _to_int(getattr(q, "tokens_limit", None), 0)
    if limit == 0 and getattr(q, "limit_tokens", None) is not None:
        limit = _to_int(getattr(q, "limit_tokens", None), 0)

    remaining = _to_int(getattr(q, "remaining", None), max(limit - used, 0))
    if remaining <= 0 and limit > 0:
        remaining = max(limit - used, 0)

    return {"used": used, "limit": limit, "remaining": remaining}


def _estimate_tokens(text: str) -> int:
    # conservative estimate ~4 chars/token
    return max(1, int(len(text or "") / 4))


@router.post("/chat")
def chat(
    payload: ChatIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    LGD — Coach V2 token debit (STABLE)
    - Source of truth bucket: feature="coach"
    - Debit is performed via services.ai_quota_service.update_quota()
      so the header (/ai-quota) reflects real consumption.
    """
    user_id = int(getattr(current_user, "id"))

    # Ensure the canonical coach bucket exists
    q = get_or_create_quota(db, user_id, feature="coach")
    snap = _quota_snapshot(q)
    if snap["limit"] > 0 and snap["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    # Generate response (provider usage may be included)
    result = generate_coach_reply(
        message=payload.message,
        mode="action",
        focus="jour",
        context=None,
        user_id=user_id,
        plan=(getattr(q, "plan", None) or "essentiel"),
    )

    reply = ""
    tokens = 0

    if isinstance(result, dict):
        reply = (result.get("reply") or "").strip()
        usage = result.get("usage") or {}
        tokens = _to_int(usage.get("total_tokens"), 0)
    else:
        reply = str(result).strip()

    if tokens <= 0:
        tokens = _estimate_tokens(payload.message) + _estimate_tokens(reply)

    updated = update_quota(db, user_id, tokens, feature="coach")
    if updated is None:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    return {
        "reply": reply,
        "tokens_consumed": tokens,
        "quota": {
            "feature": "coach",
            "plan": getattr(updated, "plan", None) or getattr(q, "plan", None) or "essentiel",
            "tokens_used": _to_int(getattr(updated, "tokens_used", None), _to_int(getattr(updated, "used_tokens", None), 0)),
            "tokens_limit": _to_int(getattr(updated, "credits", None), _to_int(getattr(updated, "tokens_limit", None), _to_int(getattr(updated, "limit_tokens", None), 0))),
            "remaining": _to_int(getattr(updated, "remaining", None), 0),
        },
    }
