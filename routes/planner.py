from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

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
# LGD PLANNER — VERSION COMPAT ÉDITEUR / MODAL MÉDIA
# ------------------------------------------------------------
# Objectif :
# - accepter les endpoints réellement appelés par le frontend :
#   GET  /planner/posts
#   POST /planner/schedule-post
#   POST /planner/schedule-carrousel
# - conserver l'ancien POST /planner/schedule
# - stocker le payload visuel complet dans SocialPost.contenu
#   sans modifier le modèle ni la DB.
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


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_datetime(payload: Dict[str, Any]) -> Optional[datetime]:
    raw = _first_text(
        payload.get("scheduled_at"),
        payload.get("date_programmee"),
        payload.get("scheduled_for"),
        payload.get("date"),
    )

    if payload.get("date") and payload.get("time"):
        raw = f"{payload.get('date')}T{payload.get('time')}"

    if not raw:
        return None

    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
        raw.replace(" ", "T"),
    ]

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.replace(tzinfo=None)
        except Exception:
            pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            pass

    return None


def _extract_contenu(payload: Dict[str, Any], forced_type: Optional[str] = None) -> Dict[str, Any]:
    raw_contenu = payload.get("contenu")
    contenu = _safe_json_loads(raw_contenu)

    if not isinstance(contenu, dict):
        contenu = {"text": str(contenu or "")}

    fmt = _first_text(
        forced_type,
        payload.get("format"),
        contenu.get("format"),
        contenu.get("type"),
    ).lower()

    if "carrousel" in fmt or "carousel" in fmt:
        final_type = "carrousel"
    else:
        final_type = "post"

    title = _first_text(
        payload.get("titre"),
        payload.get("title"),
        contenu.get("titre"),
        contenu.get("title"),
        "Publication LGD",
    )

    network = _first_text(
        payload.get("network"),
        payload.get("reseau"),
        contenu.get("network"),
        contenu.get("reseau"),
        "instagram",
    ).lower()

    preview_image = _first_text(
        payload.get("planner_preview_image"),
        payload.get("preview_image"),
        payload.get("rendered_image"),
        contenu.get("planner_preview_image"),
        contenu.get("preview_image"),
        contenu.get("rendered_image"),
    )

    # On garde volontairement les layers/slides complets si le frontend les envoie.
    # Ces données sont indispensables au modal Planner pour reconstruire le visuel.
    if isinstance(payload.get("slides"), list) and not isinstance(contenu.get("slides"), list):
        contenu["slides"] = payload.get("slides")

    if payload.get("carrousel_id") is not None and contenu.get("carrousel_id") is None:
        contenu["carrousel_id"] = payload.get("carrousel_id")

    contenu.update(
        {
            "type": final_type,
            "format": final_type,
            "titre": title,
            "title": title,
            "network": network,
            "reseau": network,
            "source": contenu.get("source") or "editor",
        }
    )

    if preview_image:
        contenu["preview_image"] = preview_image
        contenu["planner_preview_image"] = preview_image
        contenu["rendered_image"] = preview_image

    return contenu


def _extract_title(content_obj: Any) -> Optional[str]:
    if isinstance(content_obj, dict):
        return (
            content_obj.get("titre")
            or content_obj.get("title")
            or content_obj.get("name")
            or content_obj.get("text_title")
        )
    return None


def _extract_format(content_obj: Any) -> Optional[str]:
    if isinstance(content_obj, dict):
        return (
            content_obj.get("format")
            or content_obj.get("type")
            or content_obj.get("post_format")
            or content_obj.get("kind")
        )
    return None


def _extract_preview(content_obj: Any) -> str:
    if not isinstance(content_obj, dict):
        return ""
    return _first_text(
        content_obj.get("planner_preview_image"),
        content_obj.get("preview_image"),
        content_obj.get("rendered_image"),
        content_obj.get("previewImage"),
        content_obj.get("renderedImage"),
    )


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    content_obj = _safe_json_loads(getattr(post, "contenu", None))
    if not isinstance(content_obj, dict):
        content_obj = {"text": str(content_obj or "")}

    reseau = getattr(post, "reseau", None)
    date_prog = getattr(post, "date_programmee", None)
    preview = _extract_preview(content_obj)
    title = _extract_title(content_obj)
    fmt = _extract_format(content_obj)

    return {
        "id": post.id,
        "post_id": post.id,
        "planner_id": post.id,
        "user_id": post.user_id,
        "reseau": reseau,
        "network": reseau,
        "statut": getattr(post, "statut", None),
        "status": getattr(post, "statut", None),
        "titre": title,
        "title": title,
        "format": fmt,
        "contenu": content_obj,
        "content": content_obj,
        "date_programmee": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "scheduled_at": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "scheduled_for": date_prog.isoformat() if hasattr(date_prog, "isoformat") else date_prog,
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
        "preview_image": preview or None,
        "planner_preview_image": preview or None,
        "rendered_image": preview or None,
    }


def _create_planner_post(
    payload: Dict[str, Any],
    db: Session,
    user: Any,
    forced_type: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        contenu = _extract_contenu(payload, forced_type=forced_type)

        network = _first_text(
            payload.get("network"),
            payload.get("reseau"),
            contenu.get("network"),
            contenu.get("reseau"),
            "instagram",
        ).lower()

        date_programmee = _parse_datetime(payload)

        post = SocialPost(
            user_id=user.id,
            reseau=network,
            statut=_first_text(payload.get("statut"), payload.get("status"), "scheduled"),
            contenu=json.dumps(contenu, ensure_ascii=False),
            date_programmee=date_programmee,
            supprimer_apres=bool(payload.get("supprimer_apres", False)),
        )

        db.add(post)
        db.commit()
        db.refresh(post)

        return _serialize_post(post)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts")
@router.get("/posts/")
def list_planner_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.user_id == user.id)
        .order_by(SocialPost.date_programmee.desc().nullslast(), SocialPost.id.desc())
        .all()
    )
    return [_serialize_post(post) for post in posts]


@router.post("/schedule-post")
def schedule_post(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _create_planner_post(payload, db, user, forced_type="post")


@router.post("/schedule-carrousel")
def schedule_carrousel_v5(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _create_planner_post(payload, db, user, forced_type="carrousel")


@router.post("/schedule")
def schedule_legacy(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    forced_type = "carrousel" if payload.get("slides") or payload.get("carrousel_id") else None
    return _create_planner_post(payload, db, user, forced_type=forced_type)
