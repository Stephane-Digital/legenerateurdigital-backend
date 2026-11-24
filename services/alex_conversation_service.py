"""S3.B — mémoire conversationnelle bornée de Coach Alex.

Stockage isolé dans coach_profiles.profile_json (aucune migration SQL).
Les autres champs du profil Business ne doivent jamais être remplacés.
Seuls les échanges réussis du mode conversation sont enregistrés.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from sqlalchemy.orm import Session

from models.coach_profile_model import CoachProfile
from services.coach_profile_service import get_or_create

MEMORY_KEY = "alex_conversation_v1"
MAX_MESSAGES = 20  # Dix échanges au maximum ; les plus anciens sont évincés.
MAX_USER_CHARS = 1500
MAX_ASSISTANT_CHARS = 40000
MAX_CONTEXT_MESSAGES = 8
MAX_CONTEXT_CHARS = 750


def _parse_json(raw: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch if ch >= " " or ch in "\n\t" else " " for ch in value).strip()[:limit]


def _valid_messages(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = profile.get(MEMORY_KEY)
    if not isinstance(raw, dict) or not isinstance(raw.get("messages"), list):
        return []
    result: List[Dict[str, str]] = []
    for item in raw["messages"][-MAX_MESSAGES:]:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        role = item["role"]
        content = _text(item.get("content"), MAX_USER_CHARS if role == "user" else MAX_ASSISTANT_CHARS)
        if not content:
            continue
        result.append({
            "id": _text(item.get("id"), 80) or uuid4().hex,
            "role": role,
            "content": content,
            "created_at": _text(item.get("created_at"), 40),
        })
    return result


def list_conversation(db: Session, user_id: int) -> List[Dict[str, str]]:
    cp = get_or_create(db, user_id)
    return _valid_messages(_parse_json(cp.profile_json))


def recent_history(db: Session, user_id: int) -> List[Dict[str, str]]:
    """Historique structuré transmis comme rôles OpenAI, jamais comme système."""
    return [
        {"role": item["role"], "content": item["content"][:MAX_CONTEXT_CHARS]}
        for item in list_conversation(db, user_id)[-MAX_CONTEXT_MESSAGES:]
    ]


def append_exchange(db: Session, user_id: int, message: str, answer: str) -> List[Dict[str, str]]:
    user_text = _text(message, MAX_USER_CHARS)
    assistant_text = _text(answer, MAX_ASSISTANT_CHARS)
    if not user_text or not assistant_text:
        raise ValueError("Échange incomplet : sauvegarde refusée")

    # Préparer la ligne, puis verrouiller la ligne existante avant read/modify/write.
    get_or_create(db, user_id)
    cp = db.query(CoachProfile).filter(CoachProfile.user_id == int(user_id)).with_for_update().one()
    profile = _parse_json(cp.profile_json)
    existing = _valid_messages(profile)
    now = datetime.now(timezone.utc).isoformat()
    stored = (existing + [
        {"id": uuid4().hex, "role": "user", "content": user_text, "created_at": now},
        {"id": uuid4().hex, "role": "assistant", "content": assistant_text, "created_at": now},
    ])[-MAX_MESSAGES:]
    profile[MEMORY_KEY] = {"version": 1, "messages": stored}
    cp.profile_json = json.dumps(profile, ensure_ascii=False)
    cp.updated_at = datetime.utcnow()
    db.add(cp)
    db.commit()
    return stored


def clear_conversation(db: Session, user_id: int) -> None:
    get_or_create(db, user_id)
    cp = db.query(CoachProfile).filter(CoachProfile.user_id == int(user_id)).with_for_update().one()
    profile = _parse_json(cp.profile_json)
    if MEMORY_KEY in profile:
        del profile[MEMORY_KEY]
        cp.profile_json = json.dumps(profile, ensure_ascii=False)
        cp.updated_at = datetime.utcnow()
        db.add(cp)
        db.commit()
