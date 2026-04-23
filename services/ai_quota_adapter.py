from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from models.user_model import User
from services.ia_quota_admin import _norm_feature, _display_plan_from_limit


FEATURE_COACH = "coach"


def _get_quota_row(db: Session, user: User, feature: str = FEATURE_COACH):
    from models.ia_quota_model import IAQuota

    feat = _norm_feature(feature) or FEATURE_COACH
    quota = (
        db.query(IAQuota)
        .filter(IAQuota.user_id == int(user.id), IAQuota.feature == feat)
        .order_by(IAQuota.id.desc())
        .first()
    )
    return quota


def _get_limit(quota) -> int:
    for attr in ("limit_tokens", "credits", "tokens_limit"):
        if hasattr(quota, attr):
            val = getattr(quota, attr, None)
            if val is not None:
                try:
                    return int(val)
                except Exception:
                    pass
    return 0


def get_user_quota(db: Session, user: User, feature: str = FEATURE_COACH) -> Dict[str, int | str]:
    feat = _norm_feature(feature) or FEATURE_COACH
    quota = _get_quota_row(db, user, feat)
    if not quota:
        return {
            "feature": feat,
            "plan": "essentiel",
            "display_plan": "essentiel",
            "tokens_limit": 400000,
            "tokens_used": 0,
            "tokens_remaining": 400000,
            "source": "ia_quota",
        }

    limit_tokens = _get_limit(quota)
    used = int(getattr(quota, "tokens_used", 0) or 0)
    display_plan = _display_plan_from_limit(limit_tokens, getattr(quota, "plan", None))

    return {
        "feature": getattr(quota, "feature", feat),
        "plan": display_plan,
        "display_plan": display_plan,
        "tokens_limit": int(limit_tokens),
        "tokens_used": used,
        "tokens_remaining": max(limit_tokens - used, 0),
        "source": "ia_quota",
    }


def consume_tokens(db: Session, user: User, tokens: int, feature: str = FEATURE_COACH) -> Dict[str, int | str]:
    feat = _norm_feature(feature) or FEATURE_COACH
    quota = _get_quota_row(db, user, feat)
    if not quota:
        raise RuntimeError("Quota introuvable pour consume_tokens")

    quota.tokens_used = int(getattr(quota, "tokens_used", 0) or 0) + max(int(tokens), 0)
    db.commit()
    db.refresh(quota)

    limit_tokens = _get_limit(quota)
    used = int(getattr(quota, "tokens_used", 0) or 0)
    display_plan = _display_plan_from_limit(limit_tokens, getattr(quota, "plan", None))

    return {
        "feature": getattr(quota, "feature", feat),
        "plan": display_plan,
        "display_plan": display_plan,
        "tokens_limit": int(limit_tokens),
        "tokens_used": used,
        "tokens_remaining": max(limit_tokens - used, 0),
        "source": "ia_quota",
    }
