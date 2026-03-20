# C:\LGD\legenerateurdigital_backend\routes\planner_schedule.py
"""
LGD — Planner Scheduling (STABLE)

Objectifs (Phase Planner Réseaux Sociaux):
- Exposer des endpoints stables attendus par le front:
  - GET  /planner/posts
  - POST /planner/schedule-post
  - POST /planner/schedule-carrousel
- Garder la compat avec les anciens endpoints existants:
  - POST /planner/schedule  (alias schedule-carrousel)
- Ne pas casser le module /social-posts déjà utilisé en fallback.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

from models.social_post_model import SocialPost

router = APIRouter(prefix="/planner", tags=["Planner Scheduling"])


def _user_id(user: Any) -> int:
    return int(user["id"]) if isinstance(user, dict) else int(user.id)


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
        return content.get("format") or content.get("post_format") or content.get("kind")
    return None


def _extract_media_url(content: Any) -> Optional[str]:
    if not isinstance(content, dict):
        return None
    for key in ("image_url", "media_url", "imageUrl", "mediaUrl"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    slides = content.get("slides")
    if isinstance(slides, list):
        for slide in slides:
            if isinstance(slide, dict):
                for key in ("image_url", "media_url", "preview_url", "thumbnail_url"):
                    value = slide.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
    return None


def _parse_scheduled_datetime(payload: Dict[str, Any]) -> datetime:
    for key in ("scheduled_at", "scheduled_for", "date_programmee"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

    date = payload.get("date")
    time = payload.get("time")
    if isinstance(date, str) and isinstance(time, str) and date.strip() and time.strip():
        try:
            return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"date/time invalide: {e}")

    raise HTTPException(status_code=400, detail="scheduled_at (ISO) ou (date + time) requis")


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    content_obj = _safe_json_loads(getattr(post, "contenu", None))
    title = _extract_title(content_obj)
    fmt = _extract_format(content_obj)
    reseau = getattr(post, "reseau", None)
    date_prog = getattr(post, "date_programmee", None)

    return {
        "id": post.id,
        "user_id": post.user_id,
        "reseau": reseau,
        "network": reseau,
        "statut": getattr(post, "statut", None),
        "status": getattr(post, "statut", None),
        "titre": title,
        "title": title,
        "format": fmt,
        "contenu": content_obj,
        "date_programmee": date_prog,
        "scheduled_at": date_prog,
        "scheduled_for": date_prog,
        "published_at": getattr(post, "published_at", None),
        "platform_post_id": getattr(post, "platform_post_id", None),
        "publish_error": getattr(post, "publish_error", None),
        "last_publish_attempt_at": getattr(post, "last_publish_attempt_at", None),
        "media_url": _extract_media_url(content_obj),
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
    }


def _require_future(dt: datetime) -> None:
    if dt <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="La date de publication doit être dans le futur")


@router.get("/posts", response_model=List[Dict[str, Any]])
def list_planner_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.user_id == _user_id(user))
        .order_by(SocialPost.date_programmee.desc())
        .all()
    )
    return [_serialize_post(p) for p in posts]


@router.post("/schedule-post")
def schedule_post(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        network = str(payload.get("network") or payload.get("reseau") or "").strip().lower()
        if not network:
            raise HTTPException(status_code=400, detail="network manquant")

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        content_obj: Any = payload.get("contenu")
        if content_obj is None:
            content_obj = {}

        if isinstance(content_obj, str):
            content_obj = _safe_json_loads(content_obj)
            if isinstance(content_obj, str):
                content_obj = {"text": content_obj}

        if not isinstance(content_obj, dict):
            content_obj = {"value": content_obj}

        for k in ("titre", "title", "text", "caption", "format", "image_url", "media_url"):
            if payload.get(k) is not None and k not in content_obj:
                content_obj[k] = payload.get(k)

        if "type" not in content_obj:
            content_obj["type"] = content_obj.get("kind") or "post"

        post = SocialPost(
            user_id=_user_id(user),
            reseau=network,
            statut="scheduled",
            contenu=json.dumps(content_obj, ensure_ascii=False),
            date_programmee=dt,
            supprimer_apres=bool(payload.get("supprimer_apres", False)),
        )

        db.add(post)
        db.commit()
        db.refresh(post)

        return {
            "ok": True,
            "id": post.id,
            "statut": post.statut,
            "date_programmee": post.date_programmee.isoformat(),
        }

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
        network = str(payload.get("network") or payload.get("reseau") or "").strip().lower()
        if not network:
            raise HTTPException(status_code=400, detail="network manquant")

        carrousel_id = payload.get("carrousel_id") or payload.get("carousel_id")
        slides = payload.get("slides")
        if slides is None or (isinstance(slides, list) and len(slides) == 0):
            raise HTTPException(status_code=400, detail="slides manquant (array)")

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        content_obj = {
            "type": "carrousel",
            "carrousel_id": carrousel_id,
            "slides": slides,
            "caption": payload.get("caption") or payload.get("text") or payload.get("message") or "",
        }

        if payload.get("image_url") and "image_url" not in content_obj:
            content_obj["image_url"] = payload.get("image_url")
        if payload.get("media_url") and "media_url" not in content_obj:
            content_obj["media_url"] = payload.get("media_url")

        post = SocialPost(
            user_id=_user_id(user),
            reseau=network,
            statut="scheduled",
            contenu=json.dumps(content_obj, ensure_ascii=False),
            date_programmee=dt,
            supprimer_apres=bool(payload.get("supprimer_apres", False)),
        )

        db.add(post)
        db.commit()
        db.refresh(post)

        return {
            "ok": True,
            "id": post.id,
            "statut": post.statut,
            "date_programmee": post.date_programmee.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule")
def schedule_legacy_alias(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return schedule_carrousel(payload=payload, db=db, user=user)
