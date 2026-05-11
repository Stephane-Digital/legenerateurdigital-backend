from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import get_or_create_quota, update_quota
from services.user_entitlements import get_effective_plan

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


def _user_id(user) -> int:
    if isinstance(user, dict):
        return int(user["id"])
    return int(user.id)


def _user_base_plan(user) -> str:
    try:
        if isinstance(user, dict):
            return str(user.get("plan") or "essentiel")
        return str(getattr(user, "plan", None) or "essentiel")
    except Exception:
        return "essentiel"


def _limit_for_plan(plan: str) -> int:
    p = str(plan or "essentiel").lower()
    if p in {"trial", "starter", "azur"}:
        return 70_000
    if "ult" in p:
        return 2_500_000
    if "pro" in p:
        return 1_000_000
    return 400_000


def _normalize_plan_key(raw_plan: str | None, limit_value: int = 0) -> str:
    v = str(raw_plan or "").strip().lower()
    if v in {"trial", "starter", "azur", "decouverte", "découverte"}:
        return "trial"
    if v == "ultime":
        return "ultime"
    if v == "pro":
        return "pro"
    if v == "essentiel":
        if limit_value == 70_000:
            return "trial"
        return "essentiel"

    if limit_value == 70_000:
        return "trial"
    if limit_value == 2_500_000:
        return "ultime"
    if limit_value == 1_000_000:
        return "pro"
    if limit_value == 400_000:
        return "essentiel"
    return "essentiel"


def _display_plan_from_key(plan_key: str) -> str:
    if plan_key == "trial":
        return "azur"
    return plan_key


def _quota_plan_key(quota) -> str | None:
    try:
        raw = (
            getattr(quota, "plan", None)
            or getattr(quota, "plan_name", None)
            or getattr(quota, "subscription_plan", None)
        )
        limit_raw = (
            getattr(quota, "tokens_limit", None)
            or getattr(quota, "limit_tokens", None)
            or getattr(quota, "credits", None)
            or 0
        )
        return _normalize_plan_key(raw, _to_int(limit_raw, 0))
    except Exception:
        return None


def _effective_plan_key(db: Session, user) -> str:
    try:
        quota = get_or_create_quota(db, _user_id(user), feature="global")
        qp = _quota_plan_key(quota)
        if qp:
            return str(qp)
    except Exception as e:
        print("AI_QUOTA_QUOTA_PLAN_ERROR:", repr(e))

    try:
        plan, _ov = get_effective_plan(
            db,
            user_id=_user_id(user),
            base_plan=_user_base_plan(user),
        )
        return _normalize_plan_key(str(plan or _user_base_plan(user)), 0)
    except Exception as e:
        print("AI_QUOTA_EFFECTIVE_PLAN_ERROR:", repr(e))
        return _normalize_plan_key(_user_base_plan(user), 0)


def _fallback_quota(user, plan_key: str | None = None):
    effective_key = _normalize_plan_key(str(plan_key or _user_base_plan(user) or "essentiel"), 0)
    tokens_limit = _limit_for_plan(effective_key)
    display_plan = _display_plan_from_key(effective_key)

    daily_limit = 10_000 if effective_key == "trial" else max(1, int(tokens_limit / 30))

    return {
        "feature": "global",
        "plan": display_plan,
        "display_plan": display_plan,
        "plan_key": effective_key,
        "tokens_used": 0,
        "tokens_limit": tokens_limit,
        "remaining": tokens_limit,
        "daily_limit": daily_limit,
        "created_at": None,
        "reset_at": None,
    }


def serialize_quota(quota, *, plan_key_override: str | None = None, feature_override: str | None = None):
    if quota is None:
        effective_key = _normalize_plan_key(str(plan_key_override or "essentiel"), 0)
        tokens_limit = _limit_for_plan(effective_key)
        display_plan = _display_plan_from_key(effective_key)
        daily_limit = 10_000 if effective_key == "trial" else max(1, int(tokens_limit / 30))
        return {
            "feature": feature_override or "global",
            "plan": display_plan,
            "display_plan": display_plan,
            "plan_key": effective_key,
            "tokens_used": 0,
            "tokens_limit": tokens_limit,
            "remaining": tokens_limit,
            "daily_limit": daily_limit,
            "created_at": None,
            "reset_at": None,
        }

    feature = feature_override or getattr(quota, "feature", None) or "global"

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

    raw_plan = (
        plan_key_override
        or getattr(quota, "plan", None)
        or getattr(quota, "plan_name", None)
        or getattr(quota, "subscription_plan", None)
        or "essentiel"
    )
    plan_key = _normalize_plan_key(str(raw_plan), limit)

    if limit <= 0:
        limit = _limit_for_plan(plan_key)

    remaining_raw = getattr(quota, "remaining", None)
    if remaining_raw is None:
        remaining = max(limit - used, 0)
    else:
        remaining = _to_int(remaining_raw, max(limit - used, 0))

    created_at = getattr(quota, "created_at", None) or getattr(quota, "createdAt", None)
    reset_at = getattr(quota, "reset_at", None) or getattr(quota, "resetAt", None)

    display_plan = _display_plan_from_key(plan_key)
    daily_limit = 10_000 if plan_key == "trial" else max(1, int(limit / 30))

    return {
        "feature": feature,
        "plan": display_plan,
        "display_plan": display_plan,
        "plan_key": plan_key,
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
        "daily_limit": daily_limit,
        "created_at": str(created_at) if created_at else None,
        "reset_at": str(reset_at) if reset_at else None,
    }


def _get_display_quota(db: Session, user):
    effective_key = _effective_plan_key(db, user)

    try:
        quota = get_or_create_quota(db, _user_id(user), feature="global")
        data = serialize_quota(quota, plan_key_override=effective_key, feature_override="global")

        min_limit = _limit_for_plan(effective_key)
        if data["tokens_limit"] < min_limit:
            data["tokens_limit"] = min_limit
            data["remaining"] = max(min_limit - _to_int(data["tokens_used"], 0), 0)

        if data["tokens_limit"] == 70_000:
            data["plan_key"] = "trial"
            data["plan"] = "azur"
            data["display_plan"] = "azur"
            data["daily_limit"] = 10_000

        return data
    except Exception as e:
        print("AI_QUOTA_DISPLAY_ERROR:", repr(e))
        return _fallback_quota(user, effective_key)


@router.get("/")
def get_quota(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _get_display_quota(db, user)


@router.get("/global")
def get_quota_global(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _get_display_quota(db, user)


@router.post("/consume")
def consume_quota(amount: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        quota = update_quota(db, _user_id(user), amount, feature="global")
        if quota is None:
            raise HTTPException(status_code=400, detail="Quota insuffisant")
        effective_key = _effective_plan_key(db, user)
        data = serialize_quota(quota, plan_key_override=effective_key, feature_override="global")
        data["message"] = "Quota mis à jour"
        return data
    except HTTPException:
        raise
    except Exception as e:
        print("AI_QUOTA_CONSUME_ERROR:", repr(e))
        fallback = _fallback_quota(user, _effective_plan_key(db, user))
        fallback["message"] = "Quota mis à jour"
        return fallback
