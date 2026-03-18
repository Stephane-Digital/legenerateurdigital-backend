from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from models.ia_quota_model import IAQuota
from models.user_model import User
from services.ia_quota_admin import plan_default_limit, _norm_plan, _norm_feature


FEATURE_COACH = "coach"


def _get_or_create_coach_quota(db: Session, user: User) -> IAQuota:
    plan = _norm_plan(getattr(user, "plan", None) or "essentiel")
    feature = FEATURE_COACH

    quota = (
        db.query(IAQuota)
        .filter(IAQuota.user_id == int(user.id), IAQuota.feature == feature)
        # If duplicates exist (old migrations / prior bugs), always take the latest row.
        .order_by(IAQuota.id.desc())
        .first()
    )
    if quota:
        if not quota.plan:
            quota.plan = plan
        if (quota.limit_tokens or 0) <= 0:
            quota.limit_tokens = plan_default_limit(plan, feature)
        return quota

    quota = IAQuota(
        user_id=int(user.id),
        feature=feature,
        plan=plan,
        credits=0,
        tokens_used=0,
        limit_tokens=plan_default_limit(plan, feature),
        reset_at=None,
    )
    db.add(quota)
    db.commit()
    db.refresh(quota)
    return quota


def get_user_quota(db: Session, user: User, feature: str = FEATURE_COACH) -> Dict[str, int | str]:
    """
    Utilisé par /coach/quota pour afficher les jetons restants.
    """
    feat = _norm_feature(feature) or FEATURE_COACH
    if feat != FEATURE_COACH:
        # Pour l'instant, l'endpoint coach consomme uniquement 'coach'
        feat = FEATURE_COACH

    quota = _get_or_create_coach_quota(db, user)
    limit_tokens = int(quota.limit_tokens or plan_default_limit(quota.plan, quota.feature))
    used = int(quota.tokens_used or 0)
    remaining = max(limit_tokens - used, 0)

    return {
        "feature": quota.feature,
        "plan": quota.plan,
        "tokens_limit": limit_tokens,
        "tokens_used": used,
        "tokens_remaining": remaining,
        "source": "ia_quota",
    }


def consume_tokens(db: Session, user: User, tokens: int, feature: str = FEATURE_COACH) -> Dict[str, int | str]:
    """
    Appelé après une génération IA côté Coach pour incrémenter l'usage.
    """
    feat = _norm_feature(feature) or FEATURE_COACH
    if feat != FEATURE_COACH:
        feat = FEATURE_COACH

    quota = _get_or_create_coach_quota(db, user)
    quota.tokens_used = int(quota.tokens_used or 0) + max(int(tokens), 0)
    db.commit()
    db.refresh(quota)

    limit_tokens = int(quota.limit_tokens or plan_default_limit(quota.plan, quota.feature))
    used = int(quota.tokens_used or 0)
    remaining = max(limit_tokens - used, 0)

    return {
        "feature": quota.feature,
        "plan": quota.plan,
        "tokens_limit": limit_tokens,
        "tokens_used": used,
        "tokens_remaining": remaining,
        "source": "ia_quota",
    }
