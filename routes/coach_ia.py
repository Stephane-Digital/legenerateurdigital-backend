from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.coach_ai import generate_coach_reply, generate_live_strategist
from services.ai_quota_service import get_or_create_quota, update_quota

router = APIRouter(prefix="/coach", tags=["Coach IA"])


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class LiveStrategistIn(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)
    today: Optional[Dict[str, Any]] = None
    currentMission: Optional[Dict[str, Any]] = None
    generatedAtISO: Optional[str] = None


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
    - Source of truth bucket: feature="global"
    - Debit is performed via services.ai_quota_service.update_quota()
      so the header (/ai-quota) reflects real consumption.
    """
    user_id = int(getattr(current_user, "id"))

    # Ensure the canonical global bucket exists and reserve before OpenAI call.
    q = get_or_create_quota(db, user_id, feature="global")
    snap = _quota_snapshot(q)
    if snap["limit"] > 0 and snap["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    reserved_tokens = max(1_200, min(_estimate_tokens(payload.message) + 1_800, 5_000))
    reserved_quota = update_quota(db, user_id, reserved_tokens, feature="global")
    if reserved_quota is None:
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
        tokens = reserved_tokens

    return {
        "reply": reply,
        "tokens_consumed": reserved_tokens,
        "quota": {
            "feature": "global",
            "plan": getattr(reserved_quota, "plan", None) or getattr(q, "plan", None) or "essentiel",
            "tokens_used": _to_int(getattr(reserved_quota, "tokens_used", None), _to_int(getattr(reserved_quota, "used_tokens", None), 0)),
            "tokens_limit": _to_int(getattr(reserved_quota, "credits", None), _to_int(getattr(reserved_quota, "tokens_limit", None), _to_int(getattr(reserved_quota, "limit_tokens", None), 0))),
            "remaining": _to_int(getattr(reserved_quota, "remaining", None), 0),
        },
    }

@router.post("/live-strategist")
def live_strategist(
    payload: LiveStrategistIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    LGD — Alex Stratège IA Live Premium
    - Endpoint appelé par le front: /coach/live-strategist
    - Utilise le même bucket quota que le Coach IA: feature="global"
    - Réponse JSON strictement compatible avec live-strategist.ts
    """
    user_id = int(getattr(current_user, "id"))

    q = get_or_create_quota(db, user_id, feature="global")
    snap = _quota_snapshot(q)
    if snap["limit"] > 0 and snap["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    # Réserve volontairement bornée: diagnostic premium + mission + actions.
    payload_text = payload.model_dump_json(exclude_none=True)
    reserved_tokens = max(1_800, min(_estimate_tokens(payload_text) + 2_400, 6_000))

    reserved_quota = update_quota(db, user_id, reserved_tokens, feature="global")
    if reserved_quota is None:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    result = generate_live_strategist(
        payload=payload.model_dump(),
        user_id=user_id,
        user_email=getattr(current_user, "email", None),
        user_name=getattr(current_user, "name", None) or getattr(current_user, "full_name", None),
        plan=(getattr(q, "plan", None) or "essentiel"),
    )

    if not isinstance(result, dict) or result.get("success") is False:
        return {
            "success": False,
            "error": "live_strategist_unavailable",
            "tokens_consumed": reserved_tokens,
            "quota": {
                "feature": "global",
                "plan": getattr(reserved_quota, "plan", None) or getattr(q, "plan", None) or "essentiel",
                "tokens_used": _to_int(getattr(reserved_quota, "tokens_used", None), _to_int(getattr(reserved_quota, "used_tokens", None), 0)),
                "tokens_limit": _to_int(getattr(reserved_quota, "credits", None), _to_int(getattr(reserved_quota, "tokens_limit", None), _to_int(getattr(reserved_quota, "limit_tokens", None), 0))),
                "remaining": _to_int(getattr(reserved_quota, "remaining", None), 0),
            },
        }

    result["success"] = True
    result["tokens_consumed"] = reserved_tokens
    result["quota"] = {
        "feature": "global",
        "plan": getattr(reserved_quota, "plan", None) or getattr(q, "plan", None) or "essentiel",
        "tokens_used": _to_int(getattr(reserved_quota, "tokens_used", None), _to_int(getattr(reserved_quota, "used_tokens", None), 0)),
        "tokens_limit": _to_int(getattr(reserved_quota, "credits", None), _to_int(getattr(reserved_quota, "tokens_limit", None), _to_int(getattr(reserved_quota, "limit_tokens", None), 0))),
        "remaining": _to_int(getattr(reserved_quota, "remaining", None), 0),
    }
    return result

