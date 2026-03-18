from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

from services.ai_quota_service import (
    get_or_create_quota,
    update_quota,
)

router = APIRouter(prefix="/ai-quota", tags=["AI Quota"])


def _to_int(v, default=0):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def serialize_quota(quota):
    # NOTE: Returning ORM directly can serialize to {}. We normalize keys for Coach V2.
    if quota is None:
        return {
            "feature": "coach",
            "plan": "essentiel",
            "tokens_used": 0,
            "tokens_limit": 0,
            "remaining": 0,
            "created_at": None,
            "reset_at": None,
        }

    plan = (getattr(quota, 'plan', None) or getattr(quota, 'plan_name', None) or getattr(quota, 'subscription_plan', None) or '')
    feature = getattr(quota, 'feature', None) or 'coach'

    used_raw = getattr(quota, 'tokens_used', None)
    if used_raw is None:
        used_raw = getattr(quota, 'used_tokens', None)

    limit_raw = getattr(quota, 'tokens_limit', None)
    if limit_raw is None:
        limit_raw = getattr(quota, 'limit_tokens', None)
    if limit_raw is None:
        limit_raw = getattr(quota, 'credits', None)

    used = _to_int(used_raw, 0)
    limit = _to_int(limit_raw, 0)

    remaining_raw = getattr(quota, 'remaining', None)
    if remaining_raw is None:
        remaining = max(limit - used, 0)
    else:
        remaining = _to_int(remaining_raw, max(limit - used, 0))

    created_at = getattr(quota, 'created_at', None) or getattr(quota, 'createdAt', None)
    reset_at = getattr(quota, 'reset_at', None) or getattr(quota, 'resetAt', None)

    return {
        "feature": feature,
        "plan": plan,
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
        "created_at": str(created_at) if created_at else None,
        "reset_at": str(reset_at) if reset_at else None,
    }


@router.get("/")
def get_quota(db: Session = Depends(get_db), user=Depends(get_current_user)):
    quota = get_or_create_quota(db, user.id)
    return serialize_quota(quota)


# ✅ Alias attendu par certains fronts (Coach V2 / legacy) — ajout isolé
@router.get("/global")
def get_quota_global(db: Session = Depends(get_db), user=Depends(get_current_user)):
    quota = get_or_create_quota(db, user.id)
    return serialize_quota(quota)


@router.post("/consume")
def consume_quota(amount: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    quota = update_quota(db, user.id, amount)
    if quota is None:
        raise HTTPException(status_code=400, detail='Quota insuffisant')
    data = serialize_quota(quota)
    data['message'] = 'Quota mis à jour'
    return data
