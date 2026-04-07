from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.social_post_log import SocialPostLog
from routes.auth import get_current_user
from services.make_dispatcher import send_to_make

router = APIRouter(prefix="/planner", tags=["Planner Make"])

ALLOWED_CALLBACK_STATUSES = {"queued", "sent_to_make", "published", "failed"}


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
    post = dict(row)
    post["content"] = _safe_json_loads(post.get("contenu"))
    post["network"] = post.get("reseau")
    post["status"] = post.get("statut")
    post["scheduled_at"] = post.get("date_programmee")
    return post


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

    result = send_to_make(post)

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


@router.post("/make/callback")
def make_callback(payload: Dict[str, Any], db: Session = Depends(get_db)):
    shared = payload.get("secret")
    post_id = payload.get("post_id")
    status = str(payload.get("status") or "").strip().lower()
    message = str(payload.get("message") or "")
    external_id = payload.get("external_id")

    if shared is None:
        raise HTTPException(status_code=400, detail="secret manquant")
    if not post_id:
        raise HTTPException(status_code=400, detail="post_id manquant")
    if status not in ALLOWED_CALLBACK_STATUSES:
        raise HTTPException(status_code=400, detail="status callback invalide")

    row = db.execute(
        text("SELECT id, user_id, reseau, contenu FROM social_posts WHERE id = :post_id LIMIT 1"),
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
