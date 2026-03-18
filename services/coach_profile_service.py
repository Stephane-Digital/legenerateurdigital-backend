from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.coach_profile_model import CoachProfile


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _safe_json_dumps(obj: Dict[str, Any]) -> str:
    try:
        return json.dumps(obj or {}, ensure_ascii=False)
    except Exception:
        return "{}"


def get_or_create(db: Session, user_id: int) -> CoachProfile:
    cp = db.query(CoachProfile).filter(CoachProfile.user_id == int(user_id)).first()
    if cp:
        return cp

    cp = CoachProfile(user_id=int(user_id), profile_json="{}", updated_at=datetime.utcnow(), created_at=datetime.utcnow())
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


def read_profile(db: Session, user_id: int) -> Dict[str, Any]:
    cp = get_or_create(db, user_id)
    return _safe_json_loads(cp.profile_json)


def write_profile_replace(
    db: Session,
    user_id: int,
    profile: Dict[str, Any],
    intent: Optional[str] = None,
    level: Optional[str] = None,
    time_per_day: Optional[int] = None,
) -> CoachProfile:
    cp = get_or_create(db, user_id)
    cp.profile_json = _safe_json_dumps(profile)

    if intent is not None:
        cp.intent = intent
    if level is not None:
        cp.level = level
    if time_per_day is not None:
        try:
            cp.time_per_day = int(time_per_day)
        except Exception:
            cp.time_per_day = None

    cp.updated_at = datetime.utcnow()
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


def write_profile_patch(
    db: Session,
    user_id: int,
    patch: Optional[Dict[str, Any]] = None,
    intent: Optional[str] = None,
    level: Optional[str] = None,
    time_per_day: Optional[int] = None,
) -> CoachProfile:
    cp = get_or_create(db, user_id)

    current = _safe_json_loads(cp.profile_json)
    if patch and isinstance(patch, dict):
        # shallow merge
        current.update(patch)

    cp.profile_json = _safe_json_dumps(current)

    if intent is not None:
        cp.intent = intent
    if level is not None:
        cp.level = level
    if time_per_day is not None:
        try:
            cp.time_per_day = int(time_per_day)
        except Exception:
            cp.time_per_day = None

    cp.updated_at = datetime.utcnow()
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp
