from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.ia_quota_model import IAQuota
from models.user_model import User


# ---------------------------------------------------------------------
# Defaults (LGD)
# ---------------------------------------------------------------------

# Valeurs par défaut (tokens) selon plan + feature.
_DEFAULT_LIMITS: Dict[str, Dict[str, int]] = {
    "essentiel": {
        "coach": 15000,
        "editor": 15000,
        "carrousel": 15000,
        "email": 15000,
        "sales_pages": 15000,
    },
    "pro": {
        "coach": 60000,
        "editor": 60000,
        "carrousel": 60000,
        "email": 60000,
        "sales_pages": 60000,
    },
    "ultime": {
        "coach": 150000,
        "editor": 150000,
        "carrousel": 150000,
        "email": 150000,
        "sales_pages": 150000,
    },
}


def _norm_plan(plan: Optional[str]) -> str:
    p = (plan or "essentiel").strip().lower()
    if p in ("essential", "essentielle", "essentiel", "basic", "base"):
        return "essentiel"
    if p in ("pro", "professional"):
        return "pro"
    if p in ("ultime", "ultimate", "premium"):
        return "ultime"
    return "essentiel"


def _norm_feature(feature: Optional[str]) -> str:
    f = (feature or "coach").strip().lower()
    if f in ("coaching", "coach"):
        return "coach"
    if f in ("editor", "editeur", "éditeur"):
        return "editor"
    if f in ("carrousel", "carousel"):
        return "carrousel"
    if f in ("email", "emails"):
        return "email"
    if f in ("sales", "sales_pages", "salespage", "sales-page"):
        return "sales_pages"
    return f or "coach"


def plan_default_limit(plan: str, feature: str) -> int:
    p = _norm_plan(plan)
    f = _norm_feature(feature)
    return int(_DEFAULT_LIMITS.get(p, {}).get(f, 15000))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_plan(user: User) -> str:
    p = getattr(user, "plan", None)
    return _norm_plan(p)


def _quota_limit_get(quota: IAQuota, plan: str, feature: str) -> int:
    """LGD compat: depending on DB schema, the limit is stored in:
    - ia_quota.limit_tokens (newer) OR
    - ia_quota.credits (historical LGD choice)
    """
    # Newer schema
    if hasattr(quota, "limit_tokens"):
        v = getattr(quota, "limit_tokens", None)
        if v is not None and int(v) > 0:
            return int(v)

    # Historical schema
    if hasattr(quota, "credits"):
        v = getattr(quota, "credits", None)
        if v is not None and int(v) > 0:
            return int(v)

    # fallback default by plan
    return int(plan_default_limit(plan, feature))


def _quota_limit_set(quota: IAQuota, limit_tokens: int) -> None:
    """Write limit into the right column for the current DB schema."""
    if hasattr(quota, "limit_tokens"):
        setattr(quota, "limit_tokens", int(limit_tokens))
        return
    # Historical schema uses credits as limit
    if hasattr(quota, "credits"):
        setattr(quota, "credits", int(limit_tokens))
        return
    # If neither exists, we can't persist limit
    raise AttributeError("DB schema missing limit column (limit_tokens/credits)")


def _get_or_create_quota(db: Session, user_id: int, feature: str, plan: str) -> IAQuota:
    """Fetch or create the quota row.

    ✅ CRITICAL FIX:
    Previously this function *forced* quota.plan to equal user.plan on every read.
    That is exactly why your admin 'Pro/Ultime' appeared, then reverted to 'essentiel' on refresh.
    We must NEVER overwrite an existing quota.plan during reads.

    We only set plan at creation time. After that:
      - admin overrides may set quota.plan
      - coach reads must reflect quota.plan
      - user.plan may stay 'essentiel' without destroying overrides
    """
    feature = _norm_feature(feature)
    plan = _norm_plan(plan)

    quota = (
        db.query(IAQuota)
        .filter(and_(IAQuota.user_id == user_id, IAQuota.feature == feature))
        .order_by(IAQuota.id.desc())
        .first()
    )
    if quota:
        return quota

    quota = IAQuota(
        user_id=user_id,
        feature=feature,
        plan=plan,
        tokens_used=0,
        credits=0,
        reset_at=None,
    )

    # Initialize the limit in the appropriate column if possible
    try:
        _quota_limit_set(quota, plan_default_limit(plan, feature))
    except Exception:
        pass

    if hasattr(quota, "created_at"):
        quota.created_at = _utcnow()
    if hasattr(quota, "updated_at"):
        quota.updated_at = _utcnow()

    db.add(quota)
    db.commit()
    db.refresh(quota)
    return quota


def _fetch_quota_row(db: Session, user_id: int, feature: str = "coach") -> Optional[Dict[str, Any]]:
    """Preferred reader for (user_id, feature).

    IMPORTANT: if duplicates exist, we always read the latest row (id DESC)
    to avoid desync between admin and coach.
    """
    try:
        feat = _norm_feature(feature)
        quota = (
            db.query(IAQuota)
            .filter(and_(IAQuota.user_id == int(user_id), IAQuota.feature == feat))
            .order_by(IAQuota.id.desc())
            .first()
        )
        if not quota:
            return None

        plan = getattr(quota, "plan", None) or "essentiel"
        used = int(getattr(quota, "tokens_used", 0) or 0)
        limit_tokens = _quota_limit_get(quota, plan=_norm_plan(plan), feature=feat)

        return {
            "user_id": int(user_id),
            "feature": feat,
            "plan": _norm_plan(plan),
            "tokens_used": used,
            "limit_tokens": int(limit_tokens),
        }
    except Exception:
        return None


def list_quotas(
    db: Session,
    feature: Optional[str] = None,
    plan: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, Any]:
    """Admin table rows.

    ✅ CRITICAL FIX:
    The plan shown must come from the quota row (quota.plan), not be re-forced from user.plan.
    Otherwise refresh will always revert to user.plan ('essentiel').
    """
    feature = _norm_feature(feature) if feature else None
    plan = _norm_plan(plan) if plan else None

    users_query = db.query(User)

    if q:
        qq = q.strip().lower()
        if qq.isdigit():
            users_query = users_query.filter(User.id == int(qq))
        else:
            if hasattr(User, "email"):
                users_query = users_query.filter(func.lower(User.email).like(f"%{qq}%"))

    users_total = users_query.count()
    users = (
        users_query
        .order_by(User.id.asc())
        .offset((max(page, 1) - 1) * max(page_size, 1))
        .limit(max(page_size, 1))
        .all()
    )

    rows: List[Dict[str, Any]] = []
    features = [feature] if feature else ["coach"]

    for u in users:
        u_plan = _get_user_plan(u)

        for f in features:
            quota = _get_or_create_quota(db, u.id, f, u_plan)

            # ✅ Effective plan: quota.plan if present, else fallback to user.plan
            effective_plan = _norm_plan(getattr(quota, "plan", None) or u_plan)

            if plan and effective_plan != plan:
                continue

            limit_tokens_val = _quota_limit_get(quota, plan=effective_plan, feature=f)
            used = int(getattr(quota, "tokens_used", 0) or 0)

            row = {
                "user_id": u.id,
                "email": getattr(u, "email", None),
                "plan": effective_plan,
                "feature": getattr(quota, "feature", f),
                "tokens_used": used,
                "limit_tokens": int(limit_tokens_val),
                "remaining_tokens": max(int(limit_tokens_val) - used, 0),
            }
            rows.append(row)

    return {
        "items": rows,
        "total": users_total,
        "page": int(page),
        "page_size": int(page_size),
    }


def set_quota_limit(db: Session, user_id: int, limit_tokens: int, feature: str = "coach") -> Dict[str, Any]:
    feature = _norm_feature(feature)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "error": "USER_NOT_FOUND"}

    # Create row if missing, but DO NOT overwrite plan on reads
    u_plan = _get_user_plan(user)
    quota = _get_or_create_quota(db, int(user_id), feature, u_plan)

    try:
        _quota_limit_set(quota, int(limit_tokens))
    except AttributeError:
        return {"ok": False, "error": "DB_SCHEMA_MISSING_LIMIT_COLUMN"}
    except Exception as e:
        return {"ok": False, "error": f"SET_LIMIT_FAILED: {e}"}

    if hasattr(quota, "updated_at"):
        quota.updated_at = _utcnow()
    db.commit()
    db.refresh(quota)

    # Use effective plan from quota (if admin set it), else user.plan
    effective_plan = _norm_plan(getattr(quota, "plan", None) or u_plan)
    limit_val = _quota_limit_get(quota, plan=effective_plan, feature=feature)

    return {"ok": True, "user_id": int(user_id), "feature": feature, "limit_tokens": int(limit_val)}


def reset_quota(db: Session, user_id: int, feature: str = "coach") -> Dict[str, Any]:
    feature = _norm_feature(feature)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "error": "USER_NOT_FOUND"}

    u_plan = _get_user_plan(user)
    quota = _get_or_create_quota(db, int(user_id), feature, u_plan)

    quota.tokens_used = 0
    if hasattr(quota, "reset_at"):
        quota.reset_at = _utcnow()
    if hasattr(quota, "updated_at"):
        quota.updated_at = _utcnow()
    db.commit()
    db.refresh(quota)

    effective_plan = _norm_plan(getattr(quota, "plan", None) or u_plan)
    limit_val = _quota_limit_get(quota, plan=effective_plan, feature=feature)

    return {
        "ok": True,
        "user_id": int(user_id),
        "feature": feature,
        "tokens_used": int(getattr(quota, "tokens_used", 0) or 0),
        "limit_tokens": int(limit_val),
    }
