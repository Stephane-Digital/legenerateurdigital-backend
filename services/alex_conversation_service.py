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
    return compact_history(active_messages(db, user_id))


def compact_history(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Bounded excerpts: preserve user decisions and assistant endings."""
    result = []
    for item in messages[-MAX_CONTEXT_MESSAGES:]:
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _text(item.get("content"), MAX_USER_CHARS if role == "user" else MAX_ASSISTANT_CHARS)
        limit = MAX_USER_CHARS if role == "user" else MAX_CONTEXT_CHARS
        if len(content) > limit:
            marker = "\n[Extrait : passage intermédiaire omis]\n"
            head = (limit - len(marker)) // 2
            tail = limit - len(marker) - head
            content = content[:head] + marker + content[-tail:]
        if content:
            result.append({"role": role, "content": content})
    return result


def append_exchange(db: Session, user_id: int, message: str, answer: str, *, project_changed: bool = False, commercial: bool = False, active_project: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
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
    raw = profile.get(MEMORY_KEY)
    raw = raw if isinstance(raw, dict) else {}
    progress = update_progress(raw.get("progress"), user_text, assistant_text, project_changed=project_changed, commercial=commercial)
    boundary = stored[-2]["id"] if project_changed else raw.get("project_start_id")
    profile[MEMORY_KEY] = {"version": 1, "messages": stored, "progress": progress, "project_start_id": boundary}
    if isinstance(active_project, dict) and not commercial:
        profile[MEMORY_KEY]["active_project"] = dict(active_project)
    elif not project_changed and isinstance(raw.get("active_project"), dict):
        profile[MEMORY_KEY]["active_project"] = raw["active_project"]
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

# S3.C.4.7.D: bounded evidence, not inferred task completion.
def update_progress(previous: Any, message: str, answer: str, *, project_changed: bool = False, commercial: bool = False) -> List[Dict[str, str]]:
    records = []
    if not project_changed and isinstance(previous, list):
        for item in previous[-6:]:
            if isinstance(item, dict):
                request = _text(item.get("user_statement"), 240)
                response = _text(item.get("alex_excerpt"), 360)
                if request and response:
                    records.append({"user_statement": request, "alex_excerpt": response})
    if commercial:
        return records
    request = _text(message, MAX_USER_CHARS)
    response = _text(answer, MAX_ASSISTANT_CHARS)
    if request and response:
        def excerpt(value: str, limit: int) -> str:
            if len(value) <= limit:
                return value
            marker = " […] "
            head = (limit - len(marker)) // 2
            return value[:head] + marker + value[-(limit-len(marker)-head):]
        records.append({"user_statement": excerpt(request, 240), "alex_excerpt": excerpt(response, 360)})
    return records[-6:]


def active_messages(db: Session, user_id: int) -> List[Dict[str, str]]:
    cp = get_or_create(db, user_id)
    profile = _parse_json(cp.profile_json)
    messages = _valid_messages(profile)
    raw = profile.get(MEMORY_KEY)
    boundary = raw.get("project_start_id") if isinstance(raw, dict) else None
    if boundary:
        for index, item in enumerate(messages):
            if item["id"] == boundary:
                return messages[index:]
    # A boundary evicted from the bounded history precedes all remaining messages.
    return messages


def progress_context(db: Session, user_id: int, *, exclude_recent: bool = False) -> str:
    cp = get_or_create(db, user_id)
    raw = _parse_json(cp.profile_json).get(MEMORY_KEY)
    if not isinstance(raw, dict):
        return ""
    records = update_progress(raw.get("progress"), "", "")
    if exclude_recent:
        recent = active_messages(db, user_id)[-MAX_CONTEXT_MESSAGES:]
        for index in range(len(recent)-1):
            if recent[index]["role"] == "user" and recent[index+1]["role"] == "assistant":
                pair = update_progress([], recent[index]["content"], recent[index+1]["content"])
                if pair:
                    records = [item for item in records if item != pair[0]]
    return json.dumps(records, ensure_ascii=False) if records else ""
