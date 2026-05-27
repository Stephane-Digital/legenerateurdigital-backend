# legenerateurdigital_backend/routes/social_posts.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db

try:
    from routes.auth import get_current_user
except Exception:  # pragma: no cover
    from services.auth_service import get_current_user  # type: ignore

router = APIRouter(prefix="/social-posts", tags=["Social Posts"])


def _current_user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(user.id)


def _safe_json_loads(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            return value
    return value


def _extract_title(content: Any) -> Optional[str]:
    if isinstance(content, dict):
        return (
            content.get("titre")
            or content.get("title")
            or content.get("name")
            or content.get("text_title")
        )
    return None


def _extract_format(content: Any) -> Optional[str]:
    if isinstance(content, dict):
        return (
            content.get("format")
            or content.get("post_format")
            or content.get("kind")
            or content.get("type")
        )
    return None


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    content_obj = _safe_json_loads(row.get("contenu"))
    date_prog = row.get("date_programmee")

    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "reseau": row.get("reseau"),
        "network": row.get("reseau"),
        "statut": row.get("statut"),
        "status": row.get("statut"),
        "titre": _extract_title(content_obj),
        "title": _extract_title(content_obj),
        "format": _extract_format(content_obj),
        "contenu": content_obj,
        "content": content_obj,
        "date_programmee": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "scheduled_at": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "scheduled_for": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "published_at": row.get("published_at").isoformat() if hasattr(row.get("published_at"), "isoformat") else row.get("published_at"),
        "supprimer_apres": bool(row.get("supprimer_apres", False)),
        "created_at": row.get("created_at").isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
        "updated_at": row.get("updated_at").isoformat() if hasattr(row.get("updated_at"), "isoformat") else row.get("updated_at"),
    }


def _normalize_payload_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    content_obj: Any = payload.get("contenu")
    if content_obj is None:
        content_obj = payload.get("content") or {}

    if isinstance(content_obj, str):
        parsed = _safe_json_loads(content_obj)
        content_obj = {"text": parsed} if isinstance(parsed, str) else parsed

    if not isinstance(content_obj, dict):
        content_obj = {"value": content_obj}

    for key in ("titre", "title", "text", "caption", "format", "image_url", "media_url", "ui", "layers", "slides", "kind", "type"):
        if payload.get(key) is not None and key not in content_obj:
            content_obj[key] = payload.get(key)

    if "type" not in content_obj:
        content_obj["type"] = payload.get("type") or payload.get("kind") or payload.get("format") or "post"

    return content_obj


@router.get("")
@router.get("/")
def list_social_posts(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[Dict[str, Any]]:
    """
    DB-safe PROD route.
    Ne dépend pas du modèle ORM pour éviter tout crash si le modèle contient
    une colonne absente de la table Render.
    """
    sql = text(
        """
        SELECT id, user_id, reseau, statut, contenu, date_programmee,
               published_at, supprimer_apres, created_at, updated_at
        FROM social_posts
        WHERE user_id = :user_id
        ORDER BY date_programmee DESC NULLS LAST, id DESC
        """
    )
    try:
        rows = db.execute(sql, {"user_id": _current_user_id(user)}).mappings().all()
        return [_serialize_row(dict(r)) for r in rows]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"social-posts list failed: {e}")


@router.post("")
@router.post("/")
def create_social_post(payload: Dict[str, Any], db: Session = Depends(get_db), user=Depends(get_current_user)) -> Dict[str, Any]:
    """
    Création brute SocialPost, DB-safe.
    On écrit uniquement les colonnes confirmées en PROD.
    """
    try:
        reseau = str(payload.get("reseau") or payload.get("network") or "").strip().lower() or "instagram"
        statut = str(payload.get("statut") or payload.get("status") or "draft").strip().lower() or "draft"
        content_obj = _normalize_payload_content(payload)

        date_programmee = payload.get("date_programmee") or payload.get("scheduled_at") or payload.get("scheduled_for")
        supprimer_apres = bool(payload.get("supprimer_apres", False))

        sql = text(
            """
            INSERT INTO social_posts
                (user_id, reseau, statut, contenu, date_programmee, supprimer_apres, created_at, updated_at)
            VALUES
                (:user_id, :reseau, :statut, :contenu, :date_programmee, :supprimer_apres, NOW(), NOW())
            RETURNING id, user_id, reseau, statut, contenu, date_programmee,
                      published_at, supprimer_apres, created_at, updated_at
            """
        )

        row = db.execute(
            sql,
            {
                "user_id": _current_user_id(user),
                "reseau": reseau,
                "statut": statut,
                "contenu": json.dumps(content_obj, ensure_ascii=False),
                "date_programmee": date_programmee,
                "supprimer_apres": supprimer_apres,
            },
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(status_code=500, detail="Insertion social post impossible")

        return _serialize_row(dict(row))

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"social-posts create failed: {e}")
