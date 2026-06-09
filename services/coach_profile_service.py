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


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge récursif léger pour conserver les sous-objets du profil Coach.
    Important pour alex_business_project, coach_v2, real_actions_history, etc.
    """
    out = dict(base or {})

    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value

    return out


def build_default_business_project(project_type: str = "") -> Dict[str, Any]:
    """
    Structure standard du futur moteur FormAction.
    Ne force rien côté frontend : sert seulement de mémoire projet stable.
    """
    now = datetime.utcnow().isoformat()

    return {
        "version": 1,
        "project_type": project_type or "",
        "business_mode": project_type or "",
        "project_status": "DRAFT",
        "project_label": "",
        "project_name": "",
        "offer_name": "",
        "niche": "",
        "audience": "",
        "pain": "",
        "promise": "",
        "product_type": "",
        "price": "",
        "recommended_platform": "",
        "estimated_days_to_launch": None,
        "current_step": "",
        "next_action": "",
        "updated_at": now,
        "created_at": now,
    }


def normalize_business_project(value: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Normalise sans casser : complète les clés manquantes mais conserve les valeurs existantes.
    """
    base = build_default_business_project()
    if isinstance(value, dict):
        merged = _deep_merge(base, value)
    else:
        merged = base

    merged["updated_at"] = datetime.utcnow().isoformat()
    if not merged.get("created_at"):
        merged["created_at"] = merged["updated_at"]

    return merged


def patch_business_project(
    db: Session,
    user_id: int,
    patch: Optional[Dict[str, Any]] = None,
) -> CoachProfile:
    """
    Helper dédié à Coach Alex FormAction.
    Permet aux routes Coach de mémoriser un projet sans écraser le reste du profil.
    """
    cp = get_or_create(db, user_id)
    current = _safe_json_loads(cp.profile_json)

    existing = current.get("alex_business_project")
    if not isinstance(existing, dict):
        existing = {}

    next_project = normalize_business_project(_deep_merge(existing, patch or {}))
    current["alex_business_project"] = next_project

    cp.profile_json = _safe_json_dumps(current)
    cp.updated_at = datetime.utcnow()

    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp



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
        # deep merge LGD — protège les sous-objets persistants comme alex_business_project.
        current = _deep_merge(current, patch)

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
