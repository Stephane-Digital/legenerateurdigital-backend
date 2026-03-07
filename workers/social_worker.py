import os
import sys

# ✅ Ensure project root is in PYTHONPATH when running from /workers
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Set, Dict

from sqlalchemy.orm import Session
from sqlalchemy import text

from database import SessionLocal

# --------- MODELS (tolerant imports) ---------
try:
    from models.social_post_model import SocialPost  # type: ignore
except Exception:
    from models.social_post import SocialPost  # type: ignore

POLL_SECONDS = 10

# --------- Publishers (project paths) ---------
from services.publish_instagram import publish_instagram
from services.publish_facebook import publish_facebook
from services.publish_linkedin import publish_linkedin
from services.publish_tiktok import publish_tiktok


@dataclass
class PublishPostPayload:
    """Objet minimal compatible providers (attributs accessibles)."""

    content: str = ""
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    # Carrousel MVP: on prend la 1ere image si dispo
    images_base64: Optional[list] = None
    images_url: Optional[list] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_attr(obj: Any, *names: str, default=None):
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default


def _set_attr(obj: Any, **kwargs):
    for k, v in kwargs.items():
        if hasattr(obj, k):
            setattr(obj, k, v)


def _parse_content(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {"text": raw}
    return {"value": raw}


def _normalize_network(net: str) -> str:
    n = (net or "").strip().lower()
    if n in ["insta", "instagram"]:
        return "instagram"
    if n in ["fb", "facebook", "meta"]:
        return "facebook"
    if n in ["li", "linkedin"]:
        return "linkedin"
    if n in ["tt", "tiktok"]:
        return "tiktok"
    if n in ["yt", "youtube"]:
        return "youtube"
    if n in ["pin", "pinterest"]:
        return "pinterest"
    return n


# Cache columns of social_post_logs to avoid repeated information_schema queries
_LOG_COLS_CACHE: Optional[Set[str]] = None


def _get_log_columns(db: Session) -> Set[str]:
    global _LOG_COLS_CACHE
    if _LOG_COLS_CACHE is not None:
        return _LOG_COLS_CACHE

    try:
        rows = db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'social_post_logs'
                """
            )
        ).fetchall()
        cols = {r[0] for r in rows}
        _LOG_COLS_CACHE = cols
        return cols
    except Exception:
        _LOG_COLS_CACHE = set()
        return _LOG_COLS_CACHE


def _insert_log_safe(
    db: Session,
    user_id: Optional[int],
    post_id: Optional[int],
    network: Optional[str],
    content: Optional[str],
    status: str,
    message: str,
):
    """Best-effort insert: only columns that exist."""

    cols = _get_log_columns(db)
    if not cols:
        return

    payload: Dict[str, Any] = {}
    now = datetime.now(timezone.utc)

    if "user_id" in cols:
        payload["user_id"] = user_id
    if "post_id" in cols:
        payload["post_id"] = post_id
    if "status" in cols:
        payload["status"] = status
    if "message" in cols:
        payload["message"] = message
    if "created_at" in cols:
        payload["created_at"] = now

    if network is not None:
        if "network" in cols:
            payload["network"] = network
        elif "reseau" in cols:
            payload["reseau"] = network

    if content is not None:
        if "content" in cols:
            payload["content"] = content
        elif "contenu" in cols:
            payload["contenu"] = content

    if not payload:
        return

    keys = ", ".join(payload.keys())
    vals = ", ".join([f":{k}" for k in payload.keys()])

    db.execute(text(f"INSERT INTO social_post_logs ({keys}) VALUES ({vals})"), payload)


def _due_query(db: Session) -> list:
    """Planner FR + legacy EN."""

    now = _now_utc()
    q = db.query(SocialPost)
    posts: list = []

    # FR
    if hasattr(SocialPost, "statut") and hasattr(SocialPost, "date_programmee"):
        posts += (
            q.filter(getattr(SocialPost, "statut") == "scheduled")
            .filter(getattr(SocialPost, "date_programmee") != None)  # noqa: E711
            .all()
        )

    # Legacy EN
    if hasattr(SocialPost, "status") and hasattr(SocialPost, "scheduled_at"):
        posts += (
            q.filter(getattr(SocialPost, "status") == "pending")
            .filter(getattr(SocialPost, "scheduled_at") != None)  # noqa: E711
            .all()
        )

    due: list = []
    for p in posts:
        statut = _get_attr(p, "statut", "status", default=None)
        dt = _get_attr(p, "date_programmee", "scheduled_at", default=None)
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if statut in ["scheduled", "pending"] and dt <= now:
            due.append(p)

    return due


def _get_account_for(db: Session, user_id: Optional[int], network: str):
    """SAFE fetch social account without relying on SQLAlchemy model columns."""

    if user_id is None:
        raise RuntimeError("Post has no user_id (cannot resolve social account)")

    cols_rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'social_accounts'
            """
        )
    ).fetchall()
    cols = {r[0] for r in cols_rows}

    required = {"user_id", "provider", "access_token"}
    if not required.issubset(cols):
        raise RuntimeError(f"social_accounts schema missing required columns: {required - cols}")

    select_cols = ["id", "user_id", "provider", "access_token"]
    if "refresh_token" in cols:
        select_cols.append("refresh_token")
    if "expires_in" in cols:
        select_cols.append("expires_in")
    if "expires_at" in cols:
        select_cols.append("expires_at")
    if "created_at" in cols:
        select_cols.append("created_at")
    if "updated_at" in cols:
        select_cols.append("updated_at")

    sql = f"""
        SELECT {", ".join(select_cols)}
        FROM social_accounts
        WHERE user_id = :user_id AND provider = :provider
        LIMIT 1
    """

    row = db.execute(text(sql), {"user_id": user_id, "provider": network}).mappings().first()

    if not row or not row.get("access_token"):
        raise RuntimeError(f"No connected account for {network} (user_id={user_id})")

    class _Acc:
        pass

    acc = _Acc()
    for k, v in row.items():
        setattr(acc, k, v)

    return acc


def _build_publish_payload(payload: dict) -> PublishPostPayload:
    """Build a provider-friendly payload from SocialPost.contenu JSON."""

    # Normalise text
    text_value = payload.get("content") or payload.get("text") or payload.get("caption") or ""

    # Post media fields
    image_base64 = payload.get("image_base64")
    image_url = payload.get("image_url") or payload.get("media_url")

    # Carrousel MVP fields
    images_base64 = payload.get("images_base64")
    images_url = payload.get("images_url")

    # If it's a carrousel, take first image as fallback when providers don't support multi.
    if isinstance(images_base64, list) and not image_base64:
        image_base64 = images_base64[0] if images_base64 else None
    if isinstance(images_url, list) and not image_url:
        image_url = images_url[0] if images_url else None

    return PublishPostPayload(
        content=str(text_value) if text_value is not None else "",
        image_base64=image_base64,
        image_url=image_url,
        images_base64=images_base64 if isinstance(images_base64, list) else None,
        images_url=images_url if isinstance(images_url, list) else None,
    )


def _publish_one(db: Session, post: Any):
    post_id = _get_attr(post, "id", default=None)
    user_id = _get_attr(post, "user_id", default=None)

    network = _normalize_network(_get_attr(post, "reseau", "network", default=""))
    content_raw = _get_attr(post, "contenu", "content", default=None)
    payload = _parse_content(content_raw)

    # Mark publishing, commit immediately
    _set_attr(post, statut="publishing", status="publishing")
    db.add(post)
    db.commit()

    ok = False
    error: Optional[str] = None

    try:
        publish_post = _build_publish_payload(payload)

        # Provider requirements: if no media at all, some networks will fail; we keep explicit.
        if network in ["instagram", "tiktok"] and not (publish_post.image_base64 or publish_post.image_url):
            raise RuntimeError(f"{network} requires media (image_base64 or image_url)")

        account = _get_account_for(db, user_id, network)

        if network == "instagram":
            publish_instagram(publish_post, account)
        elif network == "facebook":
            publish_facebook(publish_post, account)
        elif network == "linkedin":
            publish_linkedin(publish_post, account)
        elif network == "tiktok":
            publish_tiktok(publish_post, account)
        else:
            raise RuntimeError(f"Unsupported network: {network}")

        ok = True

    except Exception as e:
        # ✅ CRITICAL: clear failed SQL transaction before any further DB ops
        try:
            db.rollback()
        except Exception:
            pass

        error = str(e)
        ok = False

    # Final status + commit ALWAYS
    try:
        if ok:
            _set_attr(post, statut="published", status="published")
        else:
            _set_attr(post, statut="failed", status="failed")

        db.add(post)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # Log best-effort
    try:
        _insert_log_safe(
            db=db,
            user_id=user_id,
            post_id=post_id,
            network=network,
            content=_get_attr(post, "contenu", "content", default=None),
            status="published" if ok else "failed",
            message="OK" if ok else (error or "Unknown error"),
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    if ok:
        print(f"[WORKER] ✅ published post id={post_id} network={network}")
    else:
        print(f"[WORKER] ❌ failed post id={post_id} network={network} error={error}")


def main():
    print("[WORKER] Social publish worker started (Planner + legacy compatible)")
    while True:
        db = SessionLocal()
        try:
            due = _due_query(db)
            if due:
                print(f"[WORKER] found {len(due)} due post(s)")
                for p in due:
                    _publish_one(db, p)
            else:
                print("[WORKER] no due posts")
        except Exception as e:
            print(f"[WORKER] ERROR: {e}")
        finally:
            db.close()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
