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
            return {}
    return {}


def _short(value: Any, limit: int = 1200) -> str:
    text_value = str(value or "")
    return text_value if len(text_value) <= limit else text_value[:limit] + "…"


def _content_summary(content: Any, fallback_title: Optional[str] = None) -> Dict[str, Any]:
    obj = _safe_json_loads(content)
    if not isinstance(obj, dict):
        obj = {}

    raw_type = str(obj.get("type") or obj.get("kind") or obj.get("format") or "post").lower()
    post_type = "carrousel" if "carrousel" in raw_type or "carousel" in raw_type else "post"

    title = (
        obj.get("titre")
        or obj.get("title")
        or obj.get("name")
        or fallback_title
        or ("Carrousel planifié" if post_type == "carrousel" else "Post planifié")
    )

    caption = obj.get("caption") or obj.get("text") or obj.get("texte") or obj.get("description") or ""

    slides = obj.get("slides") if isinstance(obj.get("slides"), list) else []
    layers = obj.get("layers") if isinstance(obj.get("layers"), list) else []

    return {
        "type": post_type,
        "format": obj.get("format") or post_type,
        "title": _short(title, 180),
        "titre": _short(title, 180),
        "caption": _short(caption, 1800),
        "text": _short(caption, 1800),
        "slides_count": len(slides),
        "layers_count": len(layers),
        "has_visual": bool(slides or layers or obj.get("has_visual")),
    }


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    content_obj = _content_summary(row.get("contenu"))
    date_prog = row.get("date_programmee")
    iso_date = date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog

    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "reseau": row.get("reseau"),
        "network": row.get("reseau"),
        "statut": row.get("statut"),
        "status": row.get("statut"),
        "titre": content_obj.get("titre"),
        "title": content_obj.get("title"),
        "format": content_obj.get("format"),
        "contenu": content_obj,
        "content": content_obj,
        "date_programmee": iso_date,
        "scheduled_at": iso_date,
        "scheduled_for": iso_date,
        "published_at": row.get("published_at").isoformat() if hasattr(row.get("published_at"), "isoformat") else row.get("published_at"),
        "supprimer_apres": bool(row.get("supprimer_apres", False)),
        "created_at": row.get("created_at").isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
        "updated_at": row.get("updated_at").isoformat() if hasattr(row.get("updated_at"), "isoformat") else row.get("updated_at"),
    }


def _safe_content_for_insert(payload: Dict[str, Any]) -> Dict[str, Any]:
    content_obj: Any = payload.get("contenu")
    if content_obj is None:
        content_obj = payload.get("content") or {}

    if isinstance(content_obj, str):
        parsed = _safe_json_loads(content_obj)
        content_obj = {"text": content_obj} if not parsed else parsed

    if not isinstance(content_obj, dict):
        content_obj = {"value": str(content_obj or "")}

    return _content_summary(content_obj, fallback_title=payload.get("titre") or payload.get("title"))


@router.get("")
@router.get("/")
def list_social_posts(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT id, user_id, reseau, statut,
               SUBSTRING(contenu FROM 1 FOR 6000) AS contenu,
               date_programmee, published_at, supprimer_apres, created_at, updated_at
        FROM social_posts
        WHERE user_id = :user_id
        ORDER BY date_programmee DESC NULLS LAST, id DESC
        LIMIT 500
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
    try:
        reseau = str(payload.get("reseau") or payload.get("network") or "instagram").strip().lower()
        statut = str(payload.get("statut") or payload.get("status") or "draft").strip().lower()
        content_obj = _safe_content_for_insert(payload)

        date_programmee = payload.get("date_programmee") or payload.get("scheduled_at") or payload.get("scheduled_for")
        supprimer_apres = bool(payload.get("supprimer_apres", False))

        sql = text(
            """
            INSERT INTO social_posts
                (user_id, reseau, statut, contenu, date_programmee, supprimer_apres, created_at, updated_at)
            VALUES
                (:user_id, :reseau, :statut, :contenu, :date_programmee, :supprimer_apres, NOW(), NOW())
            RETURNING id, user_id, reseau, statut,
                      SUBSTRING(contenu FROM 1 FOR 6000) AS contenu,
                      date_programmee, published_at, supprimer_apres, created_at, updated_at
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
