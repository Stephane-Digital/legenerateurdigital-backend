from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import get_or_create_quota, update_quota
from services.social_ai_live_service import (
    SocialAILiveError,
    estimate_tokens,
    generate_social_ai_90_day_plan,
    generate_social_ai_day_from_plan,
    generate_social_ai_live,
)
from services.user_entitlements import get_effective_plan

router = APIRouter(prefix="/social-ai/live", tags=["Social AI LIVE"])


class SocialAILivePayload(BaseModel):
    format: Optional[str] = "post"
    network: Optional[str] = "Instagram"
    goal: Optional[str] = "Autorité"
    objective: Optional[str] = None
    category: Optional[str] = "Conseils"
    tone: Optional[str] = "Premium"
    prompt: Optional[str] = None
    brief: Optional[str] = None
    context: Optional[str] = None
    offer: Optional[str] = None
    product: Optional[str] = None
    subject: Optional[str] = None
    audience: Optional[str] = None
    target: Optional[str] = None
    pain: Optional[str] = None
    promise: Optional[str] = None
    result: Optional[str] = None
    objection: Optional[str] = None
    cta: Optional[str] = None
    day_data: Optional[Dict[str, Any]] = None


class Plan90Payload(SocialAILivePayload):
    days: Optional[int] = 90


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _user_base_plan(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("plan") or "essentiel")
    return str(getattr(user, "plan", None) or "essentiel")


def _effective_plan(db: Session, user: Any) -> str:
    try:
        plan, _override = get_effective_plan(db, user_id=_user_id(user), base_plan=_user_base_plan(user))
        return str(plan or _user_base_plan(user)).lower()
    except Exception:
        return _user_base_plan(user).lower()


def _limit_for_plan(plan: str) -> int:
    p = str(plan or "essentiel").lower()
    if "cancel" in p or "inactive" in p:
        return 0
    if "trial" in p or "azur" in p or "starter" in p or "découverte" in p or "decouverte" in p:
        return 150_000
    if "ult" in p:
        return 15_000_000
    if "pro" in p:
        return 6_000_000
    return 2_000_000


def _quota_snapshot(quota: Any, *, plan_override: Optional[str] = None) -> dict:
    plan = str(plan_override or getattr(quota, "plan", None) or "essentiel").lower()
    used = _to_int(getattr(quota, "tokens_used", None), 0)
    if used == 0 and getattr(quota, "used_tokens", None) is not None:
        used = _to_int(getattr(quota, "used_tokens", None), 0)

    limit = _to_int(getattr(quota, "credits", None), 0)
    if limit == 0 and getattr(quota, "tokens_limit", None) is not None:
        limit = _to_int(getattr(quota, "tokens_limit", None), 0)
    if limit == 0 and getattr(quota, "limit_tokens", None) is not None:
        limit = _to_int(getattr(quota, "limit_tokens", None), 0)
    if limit <= 0:
        limit = _limit_for_plan(plan)

    remaining = _to_int(getattr(quota, "remaining", None), max(limit - used, 0))
    if remaining < 0:
        remaining = max(limit - used, 0)

    return {
        "feature": "global",
        "plan": plan,
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
    }



def _payload_to_dict(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    return dict(payload or {})

def _payload_has_context(payload: SocialAILivePayload) -> bool:
    values = [
        payload.prompt,
        payload.brief,
        payload.context,
        payload.offer,
        payload.product,
        payload.subject,
        payload.audience,
        payload.target,
        payload.pain,
        payload.promise,
        payload.result,
        payload.objection,
        payload.cta,
        payload.objective,
        payload.goal,
        payload.category,
    ]
    return any(str(v or "").strip() for v in values)


def _charge_quota(db: Session, user: Any, estimated_tokens: int) -> dict:
    user_id = _user_id(user)
    plan = _effective_plan(db, user)
    quota = get_or_create_quota(db, user_id, feature="global")
    before = _quota_snapshot(quota, plan_override=plan)

    if _to_int(before.get("remaining"), 0) <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "QUOTA_REACHED",
                "message": "Votre quota IA est épuisé pour ce mois.",
                "quota": before,
            },
        )

    updated = update_quota(db, user_id, max(estimated_tokens, 1), feature="global")
    if updated is None:
        latest = get_or_create_quota(db, user_id, feature="global")
        snap = _quota_snapshot(latest, plan_override=plan)
        raise HTTPException(
            status_code=402,
            detail={
                "code": "QUOTA_REACHED",
                "message": "Le quota IA restant est insuffisant pour cette génération.",
                "quota": snap,
            },
        )

    return _quota_snapshot(updated, plan_override=plan)


@router.post("/generate")
def social_ai_live_generate(
    payload: SocialAILivePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _payload_has_context(payload):
        raise HTTPException(status_code=400, detail="Le contexte de génération Social AI est vide.")

    data = _payload_to_dict(payload)

    try:
        result = generate_social_ai_live(data)
    except SocialAILiveError as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_LIVE_ERROR: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_LIVE_RUNTIME_ERROR: {exc}") from exc

    consumed = estimate_tokens(data, result)
    quota = _charge_quota(db, user, consumed)

    return {
        **result,
        "tokens_consumed": consumed,
        "quota": quota,
    }


@router.post("/plan-90-days")
def social_ai_live_plan_90_days(
    payload: Plan90Payload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _payload_has_context(payload):
        raise HTTPException(status_code=400, detail="Le contexte du plan 90 jours est vide.")

    data = _payload_to_dict(payload)
    data["days"] = 90

    try:
        result = generate_social_ai_90_day_plan(data)
    except SocialAILiveError as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_90_DAYS_ERROR: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_90_DAYS_RUNTIME_ERROR: {exc}") from exc

    consumed = estimate_tokens(data, result)
    quota = _charge_quota(db, user, consumed)

    return {
        **result,
        
        "tokens_consumed": consumed,
        "quota": quota,
    }


@router.post("/generate-day")
def social_ai_live_generate_day(
    payload: SocialAILivePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.day_data:
        raise HTTPException(status_code=400, detail="day_data est requis pour générer un jour du plan.")

    data = _payload_to_dict(payload)

    try:
        result = generate_social_ai_day_from_plan(data)
    except SocialAILiveError as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_DAY_ERROR: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SOCIAL_AI_DAY_RUNTIME_ERROR: {exc}") from exc

    consumed = estimate_tokens(data, result)
    quota = _charge_quota(db, user, consumed)

    return {
        **result,
        "tokens_consumed": consumed,
        "quota": quota,
    }
