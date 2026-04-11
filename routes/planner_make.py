from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.social_post_log import SocialPostLog
from routes.auth import get_current_user
from services.make_dispatcher import send_to_make

router = APIRouter(prefix="/planner", tags=["Planner Make"])

ALLOWED_CALLBACK_STATUSES = {"queued", "sent_to_make", "publishing", "published", "failed"}
MAKE_SHARED_SECRET = os.getenv("MAKE_SHARED_SECRET", "").strip()


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


def _require_make_secret(
    secret: Optional[str] = Query(default=None),
    x_make_secret: Optional[str] = Header(default=None, alias="X-Make-Secret"),
) -> None:
    expected = str(MAKE_SHARED_SECRET or "").strip()
    provided = str(x_make_secret or secret or "").strip()

    if not expected:
        raise HTTPException(status_code=500, detail="MAKE_SHARED_SECRET non configuré")
    if not provided:
        raise HTTPException(status_code=401, detail="secret manquant")
    if provided != expected:
        raise HTTPException(status_code=403, detail="secret invalide")


def _normalize_network(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in {"fb", "facebook"}:
        return "facebook"
    if v in {"ig", "instagram"}:
        return "instagram"
    if v in {"li", "linkedin", "linked_in"}:
        return "linkedin"
    if v in {"pin", "pinterest"}:
        return "pinterest"
    if v in {"snap", "snapchat"}:
        return "snapchat"
    return v


def _first_non_empty_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            v = value.strip()
            if v:
                return v
    return ""


def _extract_content_parts(content: Any) -> Dict[str, Any]:
    payload = _safe_json_loads(content)
    if not isinstance(payload, dict):
        text_value = str(payload or "").strip()
        return {
            "raw": payload,
            "caption": text_value,
            "base_caption": text_value,
            "cta": "",
            "hashtags": "",
            "media_url": "",
            "slides": [],
        }

    raw_caption = _first_non_empty_str(
        payload.get("caption"),
        payload.get("text"),
        payload.get("message"),
        payload.get("description"),
        payload.get("generated_caption"),
        payload.get("generated_text"),
    )

    lines = [
        line.strip()
        for line in str(raw_caption or "").replace("\r", "").split("\n")
        if line.strip()
    ]
    base_lines: List[str] = []
    hashtag_lines: List[str] = []
    cta_line = ""

    for line in lines:
        lower = line.lower()
        if line.startswith("#"):
            hashtag_lines.append(line)
            continue
        if (
            line.startswith("👉")
            or line.startswith("➡️")
            or line.startswith("✅")
            or line.startswith("🔥")
            or line.startswith("📩")
            or line.startswith("📌")
            or "contacte" in lower
            or "contactez" in lower
            or "ecris" in lower
            or "écris" in lower
            or "clique" in lower
            or "reserve" in lower
            or "réserve" in lower
            or "decouvre" in lower
            or "découvre" in lower
            or "partage" in lower
            or "enregistre" in lower
        ):
            cta_line = line
            continue
        base_lines.append(line)

    media_url = _first_non_empty_str(
        payload.get("media_url"),
        payload.get("image_url"),
        payload.get("mediaUrl"),
        payload.get("imageUrl"),
        payload.get("preview_url"),
        payload.get("previewUrl"),
        payload.get("thumbnail_url"),
        payload.get("thumbnailUrl"),
        payload.get("cover_url"),
        payload.get("coverUrl"),
    )

    slides = payload.get("slides") if isinstance(payload.get("slides"), list) else []
    if not media_url and slides:
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            media_url = _first_non_empty_str(
                slide.get("image_url"),
                slide.get("media_url"),
                slide.get("imageUrl"),
                slide.get("mediaUrl"),
                slide.get("preview_url"),
                slide.get("previewUrl"),
                slide.get("thumbnail_url"),
                slide.get("thumbnailUrl"),
                slide.get("src"),
                slide.get("url"),
            )
            if media_url:
                break

    hashtags = " ".join(dict.fromkeys(" ".join(hashtag_lines).split())).strip()
    base_caption = "\n\n".join(base_lines).strip()
    final_caption = "\n\n".join([part for part in [base_caption, cta_line.strip(), hashtags] if part]).strip()

    return {
        "raw": payload,
        "caption": final_caption,
        "base_caption": base_caption,
        "cta": cta_line.strip(),
        "hashtags": hashtags,
        "media_url": media_url,
        "slides": slides,
    }


def _serialize_make_post(row: Dict[str, Any]) -> Dict[str, Any]:
    content_parts = _extract_content_parts(row.get("contenu"))
    scheduled_at = row.get("date_programmee")
    published_at = row.get("published_at")

    return {
        "post_id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "network": _normalize_network(row.get("reseau")),
        "status": str(row.get("statut") or "scheduled"),
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "published_at": published_at.isoformat() if published_at else None,
        "caption": content_parts["caption"],
        "base_caption": content_parts["base_caption"],
        "cta": content_parts["cta"],
        "hashtags": content_parts["hashtags"],
        "media_url": content_parts["media_url"],
        "slides": content_parts["slides"],
        "content": content_parts["raw"],
        "source": "lgd_planner",
    }


def _create_log(db: Session, *, user_id: int, post_id: int, network: str, content: Any, status: str, message: str) -> None:
    db.add(
        SocialPostLog(
            user_id=int(user_id),
            post_id=int(post_id),
            network=str(network),
            content=json.dumps(content, ensure_ascii=False) if not isinstance(content, str) else content,
            status=str(status),
            message=str(message),
        )
    )


def _fetch_post(db: Session, post_id: int, user_id: int) -> Dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT id, user_id, reseau, statut, contenu, date_programmee, published_at,
                   publish_error, publish_result_raw, last_publish_attempt_at,
                   supprimer_apres, created_at, updated_at
            FROM social_posts
            WHERE id = :post_id AND user_id = :user_id
            LIMIT 1
            """
        ),
        {"post_id": int(post_id), "user_id": int(user_id)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Post introuvable")
    return dict(row)


def _apply_dispatch_result(db: Session, *, post_id: int, user_id: int, result: Dict[str, Any]) -> None:
    status = str(result.get("status") or "failed").strip().lower()
    message = str(result.get("message") or "")
    external_id = result.get("external_id")
    payload = result.get("payload")

    if status == "published":
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = :status,
                    published_at = NOW(),
                    publish_error = NULL,
                    publish_result_raw = :raw,
                    platform_post_id = COALESCE(:external_id, platform_post_id),
                    last_publish_attempt_at = NOW(),
                    updated_at = NOW()
                WHERE id = :post_id AND user_id = :user_id
                """
            ),
            {
                "status": status,
                "raw": json.dumps(result, ensure_ascii=False),
                "external_id": external_id,
                "post_id": int(post_id),
                "user_id": int(user_id),
            },
        )
    else:
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = :status,
                    publish_error = :message,
                    publish_result_raw = :raw,
                    last_publish_attempt_at = NOW(),
                    updated_at = NOW()
                WHERE id = :post_id AND user_id = :user_id
                """
            ),
            {
                "status": status,
                "message": message,
                "raw": json.dumps(result, ensure_ascii=False),
                "post_id": int(post_id),
                "user_id": int(user_id),
            },
        )

    _create_log(
        db,
        user_id=user_id,
        post_id=post_id,
        network=str(payload.get("network") if isinstance(payload, dict) else "unknown"),
        content=payload.get("content") if isinstance(payload, dict) else None,
        status=status,
        message=message or f"Dispatch result: {status}",
    )


@router.post("/posts/{post_id}/send-to-make")
def send_post_to_make(
    post_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    post = _fetch_post(db, post_id=post_id, user_id=uid)

    db.execute(
        text(
            """
            UPDATE social_posts
            SET statut = 'queued',
                last_publish_attempt_at = NOW(),
                updated_at = NOW()
            WHERE id = :post_id AND user_id = :user_id
            """
        ),
        {"post_id": int(post_id), "user_id": uid},
    )
    db.commit()

    serialized_post = _serialize_make_post(post)
    result = send_to_make(serialized_post)

    try:
        _apply_dispatch_result(db, post_id=post_id, user_id=uid, result=result)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "ok": bool(result.get("ok", False)),
        "mode": result.get("mode"),
        "status": result.get("status"),
        "message": result.get("message"),
        "external_id": result.get("external_id"),
    }


@router.post("/make/due/claim")
def claim_due_posts_for_make(
    limit: int = Query(default=20, ge=1, le=100),
    _: None = Depends(_require_make_secret),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT id, user_id, reseau, statut, contenu, date_programmee, published_at,
                   publish_error, publish_result_raw, last_publish_attempt_at,
                   supprimer_apres, created_at, updated_at
            FROM social_posts
            WHERE statut = 'scheduled'
              AND date_programmee IS NOT NULL
              AND date_programmee <= NOW()
            ORDER BY date_programmee ASC, id ASC
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    ).mappings().all()

    posts: List[Dict[str, Any]] = []
    claimed_ids: List[int] = []

    for row in rows:
        item = dict(row)
        posts.append(_serialize_make_post(item))
        claimed_ids.append(int(item["id"]))

    if claimed_ids:
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = 'queued',
                    last_publish_attempt_at = NOW(),
                    updated_at = NOW()
                WHERE id = ANY(:ids)
                """
            ),
            {"ids": claimed_ids},
        )
        db.commit()

    return {
        "ok": True,
        "count": len(posts),
        "posts": posts,
    }


@router.post("/make/callback")
def make_callback(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _: None = Depends(_require_make_secret),
):
    post_id = payload.get("post_id")
    status = str(payload.get("status") or "").strip().lower()
    message = str(payload.get("message") or "")
    external_id = payload.get("external_id")

    if not post_id:
        raise HTTPException(status_code=400, detail="post_id manquant")
    if status not in ALLOWED_CALLBACK_STATUSES:
        raise HTTPException(status_code=400, detail="status callback invalide")

    row = db.execute(
        text(
            """
            SELECT id, user_id, reseau, contenu
            FROM social_posts
            WHERE id = :post_id
            LIMIT 1
            """
        ),
        {"post_id": int(post_id)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Post introuvable")

    user_id = int(row["user_id"])
    content = _safe_json_loads(row.get("contenu"))

    if status == "published":
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = :status,
                    published_at = NOW(),
                    publish_error = NULL,
                    publish_result_raw = :raw,
                    platform_post_id = COALESCE(:external_id, platform_post_id),
                    updated_at = NOW()
                WHERE id = :post_id
                """
            ),
            {
                "status": status,
                "raw": json.dumps(payload, ensure_ascii=False),
                "external_id": external_id,
                "post_id": int(post_id),
            },
        )
    elif status in {"queued", "sent_to_make", "publishing"}:
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = :status,
                    publish_result_raw = :raw,
                    last_publish_attempt_at = NOW(),
                    updated_at = NOW()
                WHERE id = :post_id
                """
            ),
            {
                "status": status,
                "raw": json.dumps(payload, ensure_ascii=False),
                "post_id": int(post_id),
            },
        )
    else:
        db.execute(
            text(
                """
                UPDATE social_posts
                SET statut = :status,
                    publish_error = :message,
                    publish_result_raw = :raw,
                    updated_at = NOW()
                WHERE id = :post_id
                """
            ),
            {
                "status": status,
                "message": message,
                "raw": json.dumps(payload, ensure_ascii=False),
                "post_id": int(post_id),
            },
        )

    _create_log(
        db,
        user_id=user_id,
        post_id=int(post_id),
        network=str(row.get("reseau") or "unknown"),
        content=content,
        status=status,
        message=message or f"Make callback: {status}",
    )
    db.commit()

    return {"ok": True, "post_id": int(post_id), "status": status}

return {
    "ok": True,
    "count": len(posts),
    "claimed_ids": claimed_ids,
    "posts": posts,
}
