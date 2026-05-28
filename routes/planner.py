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
# LGD PLANNER — ROUTES COMPAT FRONTEND PROD
# ------------------------------------------------------------
# Frontend actuel :
# - POST /planner/schedule-post
# - POST /planner/schedule-carrousel
# - GET  /planner/posts
#
# Modèle DB actuel : SocialPost
# - reseau
# - statut
# - contenu (JSON string)
# - date_programmee
# - supprimer_apres
# ============================================================


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


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {}, ensure_ascii=False)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    raw = str(value or "").strip()
    if not raw:
        return None

    # JS ISO may end with Z
    raw = raw.replace("Z", "+00:00")

    candidates = [
        raw,
        raw.replace("T", " "),
    ]

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            # DB model usually stores naive datetime.
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except Exception:
            pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            pass

    return None


def _extract_title(content: Any) -> str:
    if isinstance(content, dict):
        return str(
            content.get("titre")
            or content.get("title")
            or content.get("name")
            or content.get("text_title")
            or "Publication LGD"
        )
    return "Publication LGD"


def _extract_format(content: Any) -> str:
    if isinstance(content, dict):
        return str(
            content.get("format")
            or content.get("type")
            or content.get("kind")
            or "post"
        )
    return "post"


def _normalize_content(payload: Dict[str, Any], forced_type: str) -> Dict[str, Any]:
    raw_content = payload.get("contenu")
    if isinstance(raw_content, str):
        parsed = _safe_json_loads(raw_content)
        content: Dict[str, Any] = parsed if isinstance(parsed, dict) else {"text": raw_content}
    elif isinstance(raw_content, dict):
        content = dict(raw_content)
    else:
        content = {}

    title = payload.get("titre") or payload.get("title") or content.get("titre") or content.get("title")
    if title:
        content.setdefault("titre", title)
        content.setdefault("title", title)

    content["type"] = forced_type
    content.setdefault("format", forced_type)

    # Preserve all visual payload fields sent by the frontend.
    for key in (
        "preview_image",
        "planner_preview_image",
        "rendered_image",
        "previewImage",
        "plannerPreviewImage",
        "renderedImage",
        "layers",
        "slides",
        "ui",
        "caption",
        "text",
        "description",
        "carrousel_id",
    ):
        if key in payload and payload.get(key) is not None and key not in content:
            content[key] = payload.get(key)

    if forced_type == "carrousel":
        slides = payload.get("slides") or content.get("slides") or []
        if isinstance(slides, list):
            content["slides"] = slides
        if payload.get("carrousel_id") is not None:
            content["carrousel_id"] = payload.get("carrousel_id")

    return content


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    content_obj = _safe_json_loads(getattr(post, "contenu", None))
    if not isinstance(content_obj, dict):
        content_obj = {"text": str(content_obj or "")}

    reseau = getattr(post, "reseau", None) or content_obj.get("network") or content_obj.get("reseau") or "instagram"
    date_programmee = getattr(post, "date_programmee", None)
    title = _extract_title(content_obj)
    fmt = _extract_format(content_obj)
    statut = getattr(post, "statut", None) or "scheduled"

    return {
        "id": post.id,
        "user_id": post.user_id,
        "reseau": reseau,
        "network": reseau,
        "statut": statut,
        "status": statut,
        "titre": title,
        "title": title,
        "format": fmt,
        "type": content_obj.get("type") or fmt,
        "contenu": content_obj,
        "content": content_obj,
        "date_programmee": date_programmee.isoformat() if hasattr(date_programmee, "isoformat") else date_programmee,
        "scheduled_at": date_programmee.isoformat() if hasattr(date_programmee, "isoformat") else date_programmee,
        "scheduled_for": date_programmee.isoformat() if hasattr(date_programmee, "isoformat") else date_programmee,
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
        # Flatten visual fields for AssistedPublishModal compatibility.
        "preview_image": content_obj.get("preview_image") or content_obj.get("planner_preview_image") or content_obj.get("rendered_image"),
        "planner_preview_image": content_obj.get("planner_preview_image") or content_obj.get("preview_image") or content_obj.get("rendered_image"),
        "rendered_image": content_obj.get("rendered_image") or content_obj.get("planner_preview_image") or content_obj.get("preview_image"),
        "layers": content_obj.get("layers"),
        "slides": content_obj.get("slides"),
        "ui": content_obj.get("ui"),
    }


def _create_planner_post(payload: Dict[str, Any], forced_type: str, db: Session, user: Any) -> Dict[str, Any]:
    network = str(payload.get("network") or payload.get("reseau") or "instagram").lower().strip()
    scheduled_at = _parse_datetime(payload.get("scheduled_at") or payload.get("date_programmee") or payload.get("date"))

    content = _normalize_content(payload, forced_type)
    content["network"] = network
    content["reseau"] = network
    if scheduled_at:
        content["scheduled_at"] = scheduled_at.isoformat()
        content["date_programmee"] = scheduled_at.isoformat()

    post = SocialPost(
        user_id=user.id,
        reseau=network,
        statut=str(payload.get("statut") or payload.get("status") or "scheduled"),
        contenu=_safe_json_dumps(content),
        date_programmee=scheduled_at,
        supprimer_apres=bool(payload.get("supprimer_apres", False)),
    )

    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.get("/posts")
def list_planner_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        posts = (
            db.query(SocialPost)
            .filter(SocialPost.user_id == user.id)
            .order_by(SocialPost.date_programmee.desc().nullslast(), SocialPost.id.desc())
            .all()
        )
        return [_serialize_post(post) for post in posts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
@router.get("/")
def list_planner_root(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return list_planner_posts(db=db, user=user)


@router.post("/schedule-post")
def schedule_post(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return _create_planner_post(payload, "post", db, user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule-carrousel")
def schedule_carrousel(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return _create_planner_post(payload, "carrousel", db, user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Legacy aliases kept for older frontend calls.
@router.post("/schedule")
def schedule_legacy(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    forced_type = "carrousel" if payload.get("slides") or payload.get("carrousel_id") else "post"
    try:
        return _create_planner_post(payload, forced_type, db, user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/posts/{post_id}/status")
@router.put("/posts/{post_id}/status")
def update_post_status(
    post_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    post = db.query(SocialPost).filter(SocialPost.id == post_id, SocialPost.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post Planner introuvable")

    post.statut = str(payload.get("statut") or payload.get("status") or post.statut or "scheduled")
    if post.statut == "published":
        try:
            post.published_at = datetime.utcnow()
        except Exception:
            pass

    db.commit()
    db.refresh(post)
    return _serialize_post(post)
