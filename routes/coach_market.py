from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.coach_market_ai import generate_market_opportunities
from services.ai_quota_service import get_or_create_quota, update_quota
try:
    from services.coach_profile_service import read_profile
except Exception:  # pragma: no cover
    read_profile = None  # type: ignore


router = APIRouter(tags=["Coach Market Opportunities"])


class MarketOpportunitiesIn(BaseModel):
    businessModel: Optional[str] = Field(default="offre_digitale", max_length=80)
    parcours: Optional[str] = Field(default="creation_produit_digital", max_length=80)
    objective: Optional[str] = Field(default="première vente", max_length=240)
    level: Optional[str] = Field(default=None, max_length=120)
    audienceSize: Optional[str] = Field(default=None, max_length=120)
    mainBlocker: Optional[str] = Field(default=None, max_length=120)
    timePerDay: Optional[Any] = None
    primaryChannel: Optional[str] = Field(default=None, max_length=180)
    existingOffer: Optional[str] = Field(default=None, max_length=4000)
    context: Dict[str, Any] = Field(default_factory=dict)


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


def _quota_snapshot(q: Any) -> Dict[str, int]:
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
    return max(1, int(len(text or "") / 4))


def _read_user_profile_context(db: Session, user_id: int) -> Dict[str, Any]:
    if read_profile is None:
        return {}
    try:
        profile = read_profile(db, user_id) or {}
        return profile if isinstance(profile, dict) else {}
    except Exception:
        return {}


def _quota_payload(q: Any, reserved_quota: Any) -> Dict[str, Any]:
    return {
        "feature": "global",
        "plan": getattr(reserved_quota, "plan", None) or getattr(q, "plan", None) or "essentiel",
        "tokens_used": _to_int(
            getattr(reserved_quota, "tokens_used", None),
            _to_int(getattr(reserved_quota, "used_tokens", None), 0),
        ),
        "tokens_limit": _to_int(
            getattr(reserved_quota, "credits", None),
            _to_int(
                getattr(reserved_quota, "tokens_limit", None),
                _to_int(getattr(reserved_quota, "limit_tokens", None), 0),
            ),
        ),
        "remaining": _to_int(getattr(reserved_quota, "remaining", None), 0),
    }


@router.post("/coach/market-opportunities")
def coach_market_opportunities(
    payload: MarketOpportunitiesIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    LGD — Alex Market Opportunities IA Live
    - Endpoint principal appelé par le bouton frontend: /coach/market-opportunities
    - Bucket quota: feature="global"
    - Retourne 5 opportunités compatibles StageRenderer.tsx
    """
    user_id = int(getattr(current_user, "id"))

    q = get_or_create_quota(db, user_id, feature="global")
    snap = _quota_snapshot(q)
    if snap["limit"] > 0 and snap["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    payload_dict = payload.model_dump()
    profile_context = _read_user_profile_context(db, user_id)

    enriched_payload: Dict[str, Any] = {
        **payload_dict,
        "profile": profile_context,
        "alex_business_project": profile_context.get("alex_business_project") or {},
    }

    payload_text = str(enriched_payload)
    reserved_tokens = max(2_500, min(_estimate_tokens(payload_text) + 3_500, 8_000))

    reserved_quota = update_quota(db, user_id, reserved_tokens, feature="global")
    if reserved_quota is None:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    result = generate_market_opportunities(
        payload=enriched_payload,
        user_id=user_id,
        user_email=getattr(current_user, "email", None),
        user_name=getattr(current_user, "name", None) or getattr(current_user, "full_name", None),
        plan=(getattr(q, "plan", None) or "essentiel"),
    )

    if not isinstance(result, dict):
        result = {"success": False, "source": "fallback_invalid", "opportunities": []}

    result["tokens_consumed"] = reserved_tokens
    result["quota"] = _quota_payload(q, reserved_quota)
    return result


@router.post("/market-opportunities")
def market_opportunities_alias(
    payload: MarketOpportunitiesIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Alias volontaire pour compatibilité frontend V7.3.
    Le vrai endpoint produit reste /coach/market-opportunities.
    """
    return coach_market_opportunities(payload=payload, current_user=current_user, db=db)
