from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.ia_quota_model import IAQuota
from models.user_model import User


def _limit_from_plan(plan: Optional[str]) -> int:
    p = (plan or "essentiel").strip().lower()
    if p in ("azur", "trial", "starter", "decouverte", "découverte"):
        return 70000
    if p in ("pro", "professional"):
        return 1_000_000
    if p in ("ultime", "ultimate", "premium"):
        return 2_500_000
    return 400_000


def _display_plan_from_limit(limit_tokens: int, raw_plan: Optional[str] = None) -> str:
    n = int(limit_tokens or 0)
    if n == 70000:
        return "azur"
    if n == 1_000_000:
        return "pro"
    if n == 2_500_000:
        return "ultime"
    if n == 400_000:
        return "essentiel"

    p = (raw_plan or "").strip().lower()
    if p in ("azur", "trial", "starter", "decouverte", "découverte"):
        return "azur"
    if p in ("pro", "professional"):
        return "pro"
    if p in ("ultime", "ultimate", "premium"):
        return "ultime"
    return "essentiel"


def _norm_plan(plan: Optional[str]) -> str:
    return _display_plan_from_limit(_limit_from_plan(plan), plan)


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
    return int(_limit_from_plan(plan))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_plan(user: User) -> str:
    p = getattr(user, "plan", None)
    return _norm_plan(p)


def _quota_limit_get(quota: IAQuota, plan: str, feature: str) -> int:
    if hasattr(quota, "limit_tokens"):
        v = getattr(quota, "limit_tokens", None)
        if v is not None and int(v) > 0:
            return int(v)
    if hasattr(quota, "credits"):
        v = getattr(quota, "credits", None)
        if v is not None and int(v) > 0:
            return int(v)
    return int(plan_default_limit(plan, feature))


def _quota_limit_set(quota: IAQuota, limit_tokens: int) -> None:
    if hasattr(quota, "limit_tokens"):
        setattr(quota, "limit_tokens", int(limit_tokens))
        return
    if hasattr(quota, "credits"):
        setattr(quota, "credits", int(limit_tokens))
        return
    raise AttributeError("DB schema missing limit column (limit_tokens/credits)")


def _get_or_create_quota(db: Session, user_id: int, feature: str, plan: str) -> IAQuota:
    feature = _norm_feature(feature)
    plan = _norm_plan(plan)

    quota = (
        db.query(IAQuota)
        .filter(and_(IAQuota.user_id == user_id, IAQuota.feature == feature))
        .order_by(IAQuota.id.desc())
        .first()
    )
    if quota:
        current_limit = _quota_limit_get(quota, plan, feature)
        effective_plan = _display_plan_from_limit(current_limit, getattr(quota, "plan", None) or plan)
        try:
            quota.plan = effective_plan
        except Exception:
            pass
        if hasattr(quota, "updated_at"):
            quota.updated_at = _utcnow()
        db.commit()
        db.refresh(quota)
        return quota

    quota = IAQuota(
        user_id=user_id,
        feature=feature,
        plan=plan,
        tokens_used=0,
        credits=0,
        reset_at=None,
    )

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

        used = int(getattr(quota, "tokens_used", 0) or 0)
        limit_tokens = _quota_limit_get(quota, plan=_norm_plan(getattr(quota, "plan", None)), feature=feat)
        effective_plan = _display_plan_from_limit(limit_tokens, getattr(quota, "plan", None))

        return {
            "user_id": int(user_id),
            "feature": feat,
            "plan": effective_plan,
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
            limit_tokens_val = _quota_limit_get(quota, plan=getattr(quota, "plan", None) or u_plan, feature=f)
            effective_plan = _display_plan_from_limit(limit_tokens_val, getattr(quota, "plan", None) or u_plan)

            if plan and effective_plan != plan:
                continue

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

    u_plan = _get_user_plan(user)
    quota = _get_or_create_quota(db, int(user_id), feature, u_plan)

    try:
        _quota_limit_set(quota, int(limit_tokens))
    except AttributeError:
        return {"ok": False, "error": "DB_SCHEMA_MISSING_LIMIT_COLUMN"}
    except Exception as e:
        return {"ok": False, "error": f"SET_LIMIT_FAILED: {e}"}

    effective_plan = _display_plan_from_limit(int(limit_tokens), getattr(quota, "plan", None) or u_plan)
    try:
        quota.plan = effective_plan
    except Exception:
        pass

    if hasattr(quota, "updated_at"):
        quota.updated_at = _utcnow()
    db.commit()
    db.refresh(quota)

    limit_val = _quota_limit_get(quota, plan=effective_plan, feature=feature)

    return {"ok": True, "user_id": int(user_id), "feature": feature, "limit_tokens": int(limit_val), "plan": effective_plan}


def reset_quota(db: Session, user_id: int, feature: str = "coach") -> Dict[str, Any]:
    feature = _norm_feature(feature)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "error": "USER_NOT_FOUND"}

    u_plan = _get_user_plan(user)
    quota = _get_or_create_quota(db, int(user_id), feature, u_plan)

    quota.tokens_used = 0
    current_limit = _quota_limit_get(quota, plan=getattr(quota, "plan", None) or u_plan, feature=feature)
    effective_plan = _display_plan_from_limit(current_limit, getattr(quota, "plan", None) or u_plan)
    try:
        quota.plan = effective_plan
    except Exception:
        pass

    if hasattr(quota, "reset_at"):
        quota.reset_at = _utcnow()
    if hasattr(quota, "updated_at"):
        quota.updated_at = _utcnow()
    db.commit()
    db.refresh(quota)

    limit_val = _quota_limit_get(quota, plan=effective_plan, feature=feature)

    return {
        "ok": True,
        "user_id": int(user_id),
        "feature": feature,
        "plan": effective_plan,
        "tokens_used": int(getattr(quota, "tokens_used", 0) or 0),
        "limit_tokens": int(limit_val),
    }
