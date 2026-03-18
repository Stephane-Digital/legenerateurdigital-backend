from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

from models.social_post_log import SocialPostLog
from models.social_post_model import SocialPost
from services.social.publish_facebook import FacebookPublishError, publish_facebook_page
from services.social.publish_instagram import InstagramPublishError, publish_instagram_image

router = APIRouter(prefix="/planner", tags=["Planner Publish"])


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


def _ensure_publish_columns(db: Session) -> None:
    db.execute(text("ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS platform_post_id VARCHAR(255);"))
    db.execute(text("ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS publish_error TEXT;"))
    db.execute(text("ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS publish_result_raw TEXT;"))
    db.execute(text("ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS last_publish_attempt_at TIMESTAMP WITHOUT TIME ZONE;"))
    db.commit()


def _normalize_network(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"fb", "facebook"}:
        return "facebook"
    if v in {"ig", "instagram"}:
        return "instagram"
    return v


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    return {
        "id": post.id,
        "user_id": post.user_id,
        "network": post.reseau,
        "status": post.statut,
        "scheduled_for": post.date_programmee.isoformat() if post.date_programmee else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "platform_post_id": post.platform_post_id,
        "publish_error": post.publish_error,
    }


def _create_log(
    db: Session,
    *,
    post: SocialPost,
    network: str,
    status: str,
    message: str,
    raw: Optional[dict] = None,
) -> None:
    raw_text = json.dumps(raw or {}, ensure_ascii=False) if raw else None

    payload: Dict[str, Any] = {
        "user_id": post.user_id,
        "post_id": post.id,
        "network": network,
        "content": raw_text,
        "status": status,
        "message": message,
    }

    # Compat avec l'ancien schéma LGD qui impose parfois action/details NOT NULL
    try:
        mapper_keys = set(SocialPostLog.__mapper__.columns.keys())
    except Exception:
        mapper_keys = set()

    if "action" in mapper_keys:
        payload["action"] = "publish"
    if "details" in mapper_keys:
        payload["details"] = raw_text or message

    log = SocialPostLog(**payload)
    db.add(log)


def _get_connection_row(db: Session, *, user_id: int, network: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT user_id, network, access_token, refresh_token, expires_at, is_active,
                   page_id, page_name, page_access_token, fb_user_id
            FROM social_connections
            WHERE user_id = :user_id AND network = :network AND is_active = TRUE
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"user_id": int(user_id), "network": network},
    ).mappings().first()
    return dict(row) if row else None


def _extract_content(post: SocialPost) -> Dict[str, Any]:
    content = _safe_json_loads(post.contenu)
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return {"text": content}
    return {"value": content}


def _first_non_empty_str(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            v = value.strip()
            if v:
                return v
    return None


def _extract_image_url_from_slides(slides: Any) -> Optional[str]:
    if not isinstance(slides, list):
        return None

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        value = _first_non_empty_str(
            slide.get("image_url"),
            slide.get("media_url"),
            slide.get("imageUrl"),
            slide.get("mediaUrl"),
            slide.get("preview_url"),
            slide.get("previewUrl"),
            slide.get("thumbnail_url"),
            slide.get("thumbnailUrl"),
        )
        if value:
            return value
    return None


def _build_publish_payload(content: Dict[str, Any]) -> Dict[str, Any]:
    caption = _first_non_empty_str(
        content.get("caption"),
        content.get("text"),
        content.get("message"),
        content.get("contenu"),
        content.get("titre"),
        content.get("title"),
        content.get("name"),
        content.get("description"),
        content.get("generated_caption"),
    )

    image_url = _first_non_empty_str(
        content.get("image_url"),
        content.get("media_url"),
        content.get("imageUrl"),
        content.get("mediaUrl"),
        content.get("preview_url"),
        content.get("previewUrl"),
        content.get("thumbnail_url"),
        content.get("thumbnailUrl"),
    )

    if not image_url:
        image_url = _extract_image_url_from_slides(content.get("slides"))

    normalized = dict(content)
    if caption and "caption" not in normalized:
        normalized["caption"] = caption
    if caption and "message" not in normalized:
        normalized["message"] = caption
    if image_url and "image_url" not in normalized:
        normalized["image_url"] = image_url
    if image_url and "media_url" not in normalized:
        normalized["media_url"] = image_url

    normalized["raw"] = content
    return normalized


def _publish_post(db: Session, post: SocialPost) -> Dict[str, Any]:
    _ensure_publish_columns(db)
    network = _normalize_network(post.reseau)
    raw_content = _extract_content(post)
    content = _build_publish_payload(raw_content)
    connection = _get_connection_row(db, user_id=post.user_id, network=network)

    if not connection:
        raise HTTPException(status_code=400, detail=f"Aucune connexion active trouvée pour {network}")

    if network == "facebook":
        page_id = str(connection.get("page_id") or "").strip()
        page_access_token = str(connection.get("page_access_token") or "").strip()
        if not page_access_token:
            page_access_token = str(connection.get("access_token") or "").strip()
        if not page_id:
            page_id = "me"

        if not _first_non_empty_str(content.get("caption"), content.get("message")) and not _first_non_empty_str(
            content.get("image_url"), content.get("media_url")
        ):
            raise HTTPException(
                status_code=400,
                detail="Aucun contenu publiable Facebook : caption/texte/image manquant",
            )

        return publish_facebook_page(
            page_id=page_id,
            page_access_token=page_access_token,
            content=content,
        )

    if network == "instagram":
        ig_user_id = str(connection.get("page_id") or "").strip()
        access_token = str(connection.get("access_token") or "").strip()

        if not _first_non_empty_str(content.get("image_url"), content.get("media_url")):
            raise HTTPException(
                status_code=400,
                detail="Aucun contenu publiable Instagram : image/media manquant",
            )

        return publish_instagram_image(
            ig_user_id=ig_user_id,
            access_token=access_token,
            content=content,
        )

    raise HTTPException(status_code=400, detail=f"Réseau non supporté pour publication réelle: {network}")


def _run_publish(db: Session, post: SocialPost) -> Dict[str, Any]:
    post.last_publish_attempt_at = datetime.utcnow()
    post.statut = "publishing"
    post.publish_error = None
    db.add(post)
    db.commit()
    db.refresh(post)

    try:
        result = _publish_post(db, post)
        post.statut = "published"
        post.published_at = datetime.utcnow()
        post.platform_post_id = str(result.get("platform_post_id") or "") or None
        post.publish_error = None
        post.publish_result_raw = json.dumps(result.get("raw_response") or result, ensure_ascii=False)
        db.add(post)
        _create_log(
            db,
            post=post,
            network=_normalize_network(post.reseau),
            status="published",
            message="Publication réussie",
            raw=result.get("raw_response") or result,
        )
        db.commit()
        db.refresh(post)
        return {"ok": True, "post": _serialize_post(post), "result": result}
    except (FacebookPublishError, InstagramPublishError, HTTPException) as e:
        db.rollback()
        post = db.query(SocialPost).filter(SocialPost.id == post.id).first()
        if post is None:
            raise
        detail = e.detail if isinstance(e, HTTPException) else str(e)
        post.statut = "failed"
        post.publish_error = detail
        post.last_publish_attempt_at = datetime.utcnow()
        db.add(post)
        _create_log(
            db,
            post=post,
            network=_normalize_network(post.reseau),
            status="failed",
            message=detail,
            raw={"error": detail},
        )
        db.commit()
        db.refresh(post)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        db.rollback()
        post = db.query(SocialPost).filter(SocialPost.id == post.id).first()
        if post is None:
            raise
        detail = str(e)
        post.statut = "failed"
        post.publish_error = detail
        post.last_publish_attempt_at = datetime.utcnow()
        db.add(post)
        _create_log(
            db,
            post=post,
            network=_normalize_network(post.reseau),
            status="failed",
            message=detail,
            raw={"error": detail},
        )
        db.commit()
        db.refresh(post)
        raise HTTPException(status_code=500, detail=detail)


@router.post("/publish-now/{post_id}")
def publish_now(
    post_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.user_id == user.id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post introuvable")
    return _run_publish(db, post)


@router.post("/publish/{post_id}")
def publish_post_alias(
    post_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return publish_now(post_id=post_id, db=db, user=user)


@router.post("/publish-due")
def publish_due(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    now = datetime.utcnow()
    posts = (
        db.query(SocialPost)
        .filter(
            SocialPost.user_id == user.id,
            SocialPost.statut.in_(["scheduled", "queued"]),
            SocialPost.date_programmee.isnot(None),
            SocialPost.date_programmee <= now,
        )
        .order_by(SocialPost.date_programmee.asc())
        .all()
    )

    results = []
    for post in posts:
        try:
            results.append(_run_publish(db, post))
        except HTTPException as e:
            results.append({"ok": False, "post_id": post.id, "error": e.detail})

    return {"ok": True, "count": len(results), "results": results}


@router.get("/publication-logs/{post_id}")
def publication_logs(
    post_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.user_id == user.id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post introuvable")

    logs = (
        db.query(SocialPostLog)
        .filter(SocialPostLog.post_id == post_id, SocialPostLog.user_id == user.id)
        .order_by(SocialPostLog.created_at.desc())
        .all()
    )

    return {
        "ok": True,
        "post": _serialize_post(post),
        "logs": [
            {
                "id": log.id,
                "status": getattr(log, "status", None),
                "message": getattr(log, "message", None),
                "network": getattr(log, "network", None),
                "content": _safe_json_loads(getattr(log, "content", None)),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
