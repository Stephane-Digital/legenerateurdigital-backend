"""Thin adapter layer used by routes.

We keep this file stable so other modules (coach, editor, etc.) can import the
same functions regardless of internal refactors.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from services.ia_quota_admin import (
    list_quotas as _list_quotas,
    reset_quota as _reset_quota,
    set_quota_limit as _set_quota_limit,
)


def list_quotas(
    db: Session,
    feature: Optional[str] = None,
    plan: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
):
    return _list_quotas(db=db, feature=feature, plan=plan, q=q, page=page, page_size=page_size)


def reset_quota(db: Session, user_id: int, feature: Optional[str] = None):
    return _reset_quota(db=db, user_id=user_id, feature=feature)


def set_quota_limit(db: Session, user_id: int, feature: Optional[str] = None, limit: int = 0):
    return _set_quota_limit(db=db, user_id=user_id, feature=feature, limit=limit)
