from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

from services.ai_quota_service import get_or_create_quota, update_quota

router = APIRouter(prefix="/ai-quota", tags=["AI Quota"])


# ======================================================
# ✅ Helpers
# ======================================================
def _to_int(v, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def serialize_quota(quota, *, feature_fallback: str = "global") -> dict:
    """
    Serialize quota ORM safely (avoid returning ORM directly).
    Normalizes keys for frontend (Coach V2 / Admin).
    """
    if quota is None:
        return {
            "feature": feature_fallback,
            "plan": "essentiel",
            "tokens_used": 0,
            "tokens_limit": 0,
            "remaining": 0,
            "created_at": None,
            "reset_at": None,
        }

    plan = (
        getattr(quota, "plan", None)
        or getattr(quota, "plan_name", None)
        or getattr(quota, "subscription_plan", None)
        or ""
    )

    feature = getattr(quota, "feature", None) or feature_fallback

    used_raw = getattr(quota, "tokens_used", None)
    if used_raw is None:
        used_raw = getattr(quota, "used_tokens", None)

    limit_raw = getattr(quota, "tokens_limit", None)
    if limit_raw is None:
        limit_raw = getattr(quota, "limit_tokens", None)
    if limit_raw is None:
        limit_raw = getattr(quota, "credits", None)

    used = _to_int(used_raw, 0)
    limit = _to_int(limit_raw, 0)

    remaining_raw = getattr(quota, "remaining", None)
    if remaining_raw is None:
        remaining = max(limit - used, 0)
    else:
        remaining = _to_int(remaining_raw, max(limit - used, 0))

    created_at = getattr(quota, "created_at", None) or getattr(quota, "createdAt", None)
    reset_at = getattr(quota, "reset_at", None) or getattr(quota, "resetAt", None)

    return {
        "feature": feature,
        "plan": plan,
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
        "created_at": str(created_at) if created_at else None,
        "reset_at": str(reset_at) if reset_at else None,
    }


def _svc_get_or_create(db: Session, user_id: int, feature: str):
    """
    Calls service with feature if supported, otherwise fallback.
    Also best-effort sets quota.feature when possible (without breaking).
    """
    try:
        quota = get_or_create_quota(db, user_id, feature=feature)  # type: ignore
    except TypeError:
        quota = get_or_create_quota(db, user_id)  # type: ignore

        # best-effort tag feature if model supports it
        try:
            if quota is not None and hasattr(quota, "feature"):
                setattr(quota, "feature", feature)
                db.add(quota)
                db.commit()
                db.refresh(quota)
        except Exception:
            pass

    return quota


def _svc_update(db: Session, user_id: int, amount: int, feature: str):
    """
    Calls update service with feature if supported, otherwise fallback.
    Note: ai_quota_service.update_quota is allowed to force 'global' internally.
    """
    try:
        return update_quota(db, user_id, amount, feature=feature)  # type: ignore
    except TypeError:
        return update_quota(db, user_id, amount)  # type: ignore


# ======================================================
# ✅ Routes — GLOBAL QUOTA (SOURCE OF TRUTH)
# ======================================================
@router.get("/global")
def get_global_quota(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    LGD SOURCE OF TRUTH
    1 USER = 1 GLOBAL QUOTA
    NO SUM
    NO FEATURE ADDITION
    """
    quota = _svc_get_or_create(db, int(user.id), "global")
    return JSONResponse(content=serialize_quota(quota, feature_fallback="global"))


# ======================================================
# ✅ Consume (kept compatible with feature query param)
# ======================================================
@router.post("/consume")
def consume_quota(
    amount: int = Query(..., description="Tokens to consume"),
    feature: str = Query("global"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    amt = int(amount or 0)
    if amt <= 0:
        amt = 1

    quota = _svc_update(db, int(user.id), amt, feature)
    if quota is None:
        raise HTTPException(status_code=400, detail="Quota insuffisant")

    data = serialize_quota(quota, feature_fallback=feature)
    return {
        "message": "Quota mis à jour",
        "remaining": data["remaining"],
        "tokens_used": data["tokens_used"],
        "tokens_limit": data["tokens_limit"],
        "feature": data["feature"],
        "plan": data["plan"],
    }
