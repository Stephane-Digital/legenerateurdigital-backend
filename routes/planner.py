from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db

try:
    from routes.auth import get_current_user
except Exception:  # pragma: no cover
    from services.auth_service import get_current_user  # type: ignore

try:
    from models.social_post_model import SocialPost
except Exception:  # pragma: no cover
    from models.social_post import SocialPost  # type: ignore


router = APIRouter(prefix="/planner", tags=["Planner"])


# ============================================================
# LGD PLANNER — SAFE BACKEND COMPAT
# Compatible modèle réel :
# - reseau
# - contenu
# - statut
# - date_programmee
# - supprimer_apres
#
# Objectif :
# - stopper les 500 / 502
# - conserver le payload complet dans contenu JSON
# - exposer /planner/posts pour le frontend Planner
# - exposer /planner/schedule-post et /planner/schedule-carrousel
# ============================================================


def _get_user_id(user: Any) -> int:
    if isinstance(user, dict):
        raw = user.get("id") or user.get("user_id") or user.get("sub")
    else:
        raw = getattr(user, "id", None) or getattr(user, "user_id", None)

    try:
        uid = int(raw)
    except Exception:
        uid = 0

    if uid <= 0:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié")
    return uid


def _safe_json_loads(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {"text": value}
    return value


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {}, ensure_ascii=False)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Compat ISO envoyé par le frontend :
    # 2026-05-28T21:56:00+02:00
    # 2026-05-28T21:56
    # 2026-05-28 21:56
    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text.replace("T", " "),
    ]

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            # SQLAlchemy/Postgres actuel accepte mieux du naive dans ce projet.
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except Exception:
            pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.replace("T", " "), fmt)
        except Exception:
            pass

    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            v = value.strip()
            if v:
                return v
    return ""


def _extract_title(content: Any) -> str:
    if isinstance(content, dict):
        return _first_text(
            content.get("titre"),
            content.get("title"),
            content.get("name"),
            content.get("text_title"),
            content.get("caption"),
            content.get("text"),
        )
    return ""


def _extract_format(content: Any) -> str:
    if isinstance(content, dict):
        return _first_text(
            content.get("format"),
            content.get("type"),
            content.get("kind"),
            content.get("post_format"),
        )
    return ""


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    content_obj = _safe_json_loads(getattr(post, "contenu", None))

    reseau = getattr(post, "reseau", None) or ""
    statut = getattr(post, "statut", None) or "scheduled"
    date_programmee = getattr(post, "date_programmee", None)

    title = _extract_title(content_obj) or "Publication LGD"
    fmt = _extract_format(content_obj) or "post"

    scheduled_iso = (
        date_programmee.isoformat()
        if hasattr(date_programmee, "isoformat")
        else date_programmee
    )

    return {
        "id": getattr(post, "id", None),
        "user_id": getattr(post, "user_id", None),
        "reseau": reseau,
        "network": reseau,
        "statut": statut,
        "status": statut,
        "titre": title,
        "title": title,
        "format": fmt,
        "contenu": content_obj,
        "content": content_obj,
        "date_programmee": scheduled_iso,
        "scheduled_at": scheduled_iso,
        "scheduled_for": scheduled_iso,
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
    }


def _build_content_from_payload(payload: Dict[str, Any], forced_type: Optional[str] = None) -> Dict[str, Any]:
    contenu = payload.get("contenu")
    if isinstance(contenu, str):
        contenu = _safe_json_loads(contenu)
    if not isinstance(contenu, dict):
        contenu = {}

    post_type = forced_type or payload.get("format") or contenu.get("type") or "post"

    merged: Dict[str, Any] = {
        **contenu,
        "type": "carrousel" if str(post_type).lower().startswith("carrousel") else "post",
        "format": payload.get("format") or contenu.get("format") or post_type,
        "titre": payload.get("titre") or payload.get("title") or contenu.get("titre") or contenu.get("title") or "Publication LGD",
        "title": payload.get("titre") or payload.get("title") or contenu.get("title") or contenu.get("titre") or "Publication LGD",
        "caption": payload.get("caption") or contenu.get("caption") or contenu.get("text") or "",
        "text": payload.get("text") or contenu.get("text") or contenu.get("caption") or "",
        "network": payload.get("network") or payload.get("reseau") or contenu.get("network") or "instagram",
        "scheduled_at": payload.get("scheduled_at") or payload.get("date_programmee") or contenu.get("scheduled_at"),
    }

    # Conservation complète des données visuelles.
    for key in (
        "layers",
        "slides",
        "ui",
        "canvas",
        "draft",
        "payload",
        "preview_image",
        "planner_preview_image",
        "rendered_image",
        "previewImage",
        "plannerPreviewImage",
        "renderedImage",
        "image_url",
        "media_url",
        "thumbnail_url",
        "carrousel_id",
    ):
        if key in payload and payload.get(key) is not None:
            merged[key] = payload.get(key)
        if isinstance(contenu, dict) and key in contenu and contenu.get(key) is not None:
            merged[key] = contenu.get(key)

    if "slides" not in merged and isinstance(payload.get("slides"), list):
        merged["slides"] = payload["slides"]

    return merged


def _create_planner_post(
    payload: Dict[str, Any],
    db: Session,
    user: Any,
    forced_type: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _get_user_id(user)

    network = _first_text(payload.get("network"), payload.get("reseau"), "instagram").lower()
    scheduled_at = _parse_datetime(
        payload.get("scheduled_at")
        or payload.get("date_programmee")
        or payload.get("date")
    )

    if scheduled_at is None:
        # Sécurité : éviter un 500 si le frontend oublie la date.
        scheduled_at = datetime.utcnow()

    content = _build_content_from_payload(payload, forced_type=forced_type)

    post = SocialPost(
        user_id=user_id,
        reseau=network,
        statut=payload.get("statut") or payload.get("status") or "scheduled",
        contenu=_safe_json_dumps(content),
        date_programmee=scheduled_at,
        supprimer_apres=bool(payload.get("supprimer_apres", False)),
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    return _serialize_post(post)


@router.get("")
@router.get("/")
@router.get("/posts")
def list_planner_posts(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    user_id = _get_user_id(user)

    posts = (
        db.query(SocialPost)
        .filter(SocialPost.user_id == user_id)
        .order_by(SocialPost.date_programmee.asc())
        .all()
    )

    return [_serialize_post(post) for post in posts]


@router.post("/schedule-post")
def schedule_post(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    try:
        return _create_planner_post(payload, db=db, user=user, forced_type="post")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/schedule-carrousel")
def schedule_carrousel(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    try:
        return _create_planner_post(payload, db=db, user=user, forced_type="carrousel")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/schedule")
def schedule_legacy(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    try:
        forced_type = "carrousel" if payload.get("slides") or payload.get("carrousel_id") else "post"

        # Compat ancien format date + time.
        if payload.get("date") and payload.get("time") and not payload.get("scheduled_at"):
            payload = {
                **payload,
                "scheduled_at": f"{payload.get('date')}T{payload.get('time')}:00",
            }

        return _create_planner_post(payload, db=db, user=user, forced_type=forced_type)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{post_id}/status")
def update_planner_post_status(
    post_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    user_id = _get_user_id(user)
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.user_id == user_id)
        .first()
    )

    if not post:
        raise HTTPException(status_code=404, detail="Post introuvable")

    post.statut = payload.get("statut") or payload.get("status") or post.statut
    db.commit()
    db.refresh(post)

    return _serialize_post(post)


@router.delete("/{post_id}")
def delete_planner_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    user_id = _get_user_id(user)
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.user_id == user_id)
        .first()
    )

    if not post:
        raise HTTPException(status_code=404, detail="Post introuvable")

    db.delete(post)
    db.commit()
    return {"ok": True}
