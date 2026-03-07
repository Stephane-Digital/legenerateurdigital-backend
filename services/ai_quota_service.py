from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy.orm import Session

# ======================================================
# LGD — AI QUOTA SERVICE (STABLE)
# - Canonical bucket for Coach V2: feature="coach"
# - IAQuota model columns (current DB):
#   - credits (int)  -> limit tokens (MONTHLY cap)
#   - tokens_used (int)
#   - plan (str)
#   - feature (str)
#
# Soft-daily + hard-monthly:
# - HARD MONTHLY: credits is the monthly cap
# - SOFT DAILY: if DB/model has daily_* columns, enforce daily cap = credits/30
#   (best-effort, no schema change required)
# ======================================================

try:
    from models.ia_quota_model import IAQuota as QuotaModel  # type: ignore
except Exception:
    try:
        from models.ia_quota_model import IaQuota as QuotaModel  # type: ignore
    except Exception:
        QuotaModel = None  # type: ignore


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


def _default_limit_for_plan(plan: str) -> int:
    # ✅ LGD plan limits (MONTHLY caps)
    p = (plan or "").lower()
    if "ult" in p:
        return 2_500_000
    if "pro" in p:
        return 1_000_000
    return 400_000


def _get_used(quota: Any) -> int:
    if hasattr(quota, "tokens_used"):
        return _to_int(getattr(quota, "tokens_used", 0), 0)
    if hasattr(quota, "used_tokens"):
        return _to_int(getattr(quota, "used_tokens", 0), 0)
    return 0


def _set_used(quota: Any, value: int) -> None:
    v = int(value)
    if hasattr(quota, "tokens_used"):
        setattr(quota, "tokens_used", v)
        return
    if hasattr(quota, "used_tokens"):
        setattr(quota, "used_tokens", v)
        return


def _get_limit(quota: Any) -> int:
    # IAQuota model uses credits
    if hasattr(quota, "credits") and getattr(quota, "credits", None) is not None:
        return _to_int(getattr(quota, "credits", 0), 0)
    # tolerate legacy columns
    if hasattr(quota, "tokens_limit") and getattr(quota, "tokens_limit", None) is not None:
        return _to_int(getattr(quota, "tokens_limit", 0), 0)
    if hasattr(quota, "limit_tokens") and getattr(quota, "limit_tokens", None) is not None:
        return _to_int(getattr(quota, "limit_tokens", 0), 0)
    return 0


def _set_limit(quota: Any, value: int) -> None:
    v = int(value)
    if hasattr(quota, "credits"):
        setattr(quota, "credits", v)
        return
    if hasattr(quota, "tokens_limit"):
        setattr(quota, "tokens_limit", v)
        return
    if hasattr(quota, "limit_tokens"):
        setattr(quota, "limit_tokens", v)
        return


def _set_remaining(quota: Any, remaining: int) -> None:
    # Remaining is optional — only set if the column exists
    if hasattr(quota, "remaining"):
        try:
            setattr(quota, "remaining", int(remaining))
        except Exception:
            pass


def _today_key() -> str:
    # YYYY-MM-DD (server local time)
    return datetime.date.today().isoformat()


# ---- Optional daily tracking (best-effort, schema tolerant) ----

_DAILY_USED_FIELDS = ("daily_used", "tokens_used_daily", "used_today", "tokens_used_today")
_DAILY_DATE_FIELDS = ("daily_date", "daily_reset_date", "used_today_date", "tokens_used_today_date")


def _get_daily_used(quota: Any) -> int:
    for k in _DAILY_USED_FIELDS:
        if hasattr(quota, k) and getattr(quota, k, None) is not None:
            return _to_int(getattr(quota, k, 0), 0)
    return 0


def _set_daily_used(quota: Any, value: int) -> None:
    v = int(value)
    for k in _DAILY_USED_FIELDS:
        if hasattr(quota, k):
            try:
                setattr(quota, k, v)
                return
            except Exception:
                pass


def _get_daily_date(quota: Any) -> str:
    for k in _DAILY_DATE_FIELDS:
        if hasattr(quota, k) and getattr(quota, k, None):
            return str(getattr(quota, k))
    return ""


def _set_daily_date(quota: Any, value: str) -> None:
    for k in _DAILY_DATE_FIELDS:
        if hasattr(quota, k):
            try:
                setattr(quota, k, value)
                return
            except Exception:
                pass


def get_or_create_quota(db: Session, user_id: int, feature: str = "coach"):
    if QuotaModel is None:
        raise RuntimeError("QuotaModel introuvable (models.ia_quota_model)")

    feature = (feature or "coach").strip() or "coach"

    q = (
        db.query(QuotaModel)
        .filter(QuotaModel.user_id == int(user_id))  # type: ignore
        .filter(QuotaModel.feature == feature)  # type: ignore
        .first()
    )

    if q:
        # Ensure monthly limit exists if credits is unset/0
        limit = _get_limit(q)
        if limit <= 0:
            plan = str(getattr(q, "plan", None) or "essentiel")
            _set_limit(q, _default_limit_for_plan(plan))
            _set_remaining(q, max(_get_limit(q) - _get_used(q), 0))
            db.add(q)
            db.commit()
            db.refresh(q)
        return q

    q = QuotaModel()  # type: ignore
    setattr(q, "user_id", int(user_id))
    try:
        setattr(q, "feature", feature)
    except Exception:
        pass

    # default plan (do NOT override if model has default)
    plan = getattr(q, "plan", None) or "essentiel"
    try:
        if hasattr(q, "plan"):
            setattr(q, "plan", plan)
    except Exception:
        pass

    default_limit = _default_limit_for_plan(str(plan))
    _set_limit(q, default_limit)

    _set_used(q, 0)
    _set_remaining(q, default_limit)

    # init daily fields if available
    today = _today_key()
    _set_daily_date(q, today)
    _set_daily_used(q, 0)

    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def update_quota(db: Session, user_id: int, amount: int, feature: str = "coach"):
    amt = _to_int(amount, 0)
    if amt <= 0:
        amt = 1

    q = get_or_create_quota(db, int(user_id), feature=feature)

    limit = _get_limit(q)  # monthly cap
    used = _get_used(q)

    # --- SOFT DAILY + HARD MONTHLY ---
    daily_supported = any(hasattr(q, k) for k in _DAILY_USED_FIELDS) or any(
        hasattr(q, k) for k in _DAILY_DATE_FIELDS
    )
    daily_limit = max(1, int(limit // 30)) if limit > 0 else 0

    if daily_supported and daily_limit > 0:
        today = _today_key()
        last_day = _get_daily_date(q)
        if last_day != today:
            _set_daily_used(q, 0)
            _set_daily_date(q, today)

        daily_used = _get_daily_used(q)
        if daily_used + amt > daily_limit:
            return None

    # Hard monthly cap
    if limit > 0 and used + amt > limit:
        return None

    new_used = used + amt
    _set_used(q, new_used)

    if daily_supported and daily_limit > 0:
        _set_daily_used(q, _get_daily_used(q) + amt)
        _set_daily_date(q, _today_key())

    if limit > 0:
        _set_remaining(q, max(limit - new_used, 0))

    db.add(q)
    db.commit()
    db.refresh(q)
    return q
