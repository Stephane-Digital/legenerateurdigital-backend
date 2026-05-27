"""
LGD — Planner Scheduling (PROD DB-safe / lightweight)
- Compatible with current Render DB schema for social_posts
- Avoids ORM hydration on list routes
- Avoids returning/storing huge Canva/base64 payloads that can crash Render
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/planner", tags=["Planner Scheduling"])

ALLOWED_NETWORKS = {"instagram", "facebook", "linkedin", "tiktok", "youtube", "pinterest"}
ALLOWED_STATUSES = {"draft", "scheduled", "queued", "sent_to_make", "published", "failed"}


def _user_id(user: Any) -> int:
    return int(user["id"]) if isinstance(user, dict) else int(user.id)


def _normalize_network(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in {"ig", "instagram"}:
        return "instagram"
    if v in {"fb", "facebook"}:
        return "facebook"
    if v in {"li", "linkedin", "linked_in"}:
        return "linkedin"
    return v or "instagram"


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


def _strip_heavy(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return None

    if isinstance(value, str):
        if value.startswith("data:image/") or len(value) > 5000:
            return ""
        return value

    if isinstance(value, list):
        return [_strip_heavy(v, depth + 1) for v in value[:30]]

    if isinstance(value, dict):
        blocked = {
            "preview_image",
            "planner_preview_image",
            "runtimeImages",
            "runtime_images",
            "imageData",
            "image_data",
            "dataUrl",
            "data_url",
            "base64",
            "blob",
        }
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if k in blocked:
                continue
            if k in {"src", "url", "image_url", "media_url"} and isinstance(v, str) and v.startswith("data:image/"):
                continue
            out[k] = _strip_heavy(v, depth + 1)
        return out

    return value


def _content_summary(content: Any, fallback_title: Optional[str] = None, fallback_type: str = "post") -> Dict[str, Any]:
    obj = _safe_json_loads(content)
    if not isinstance(obj, dict):
        obj = {}

    obj = _strip_heavy(obj) or {}
    if not isinstance(obj, dict):
        obj = {}

    raw_type = str(obj.get("type") or obj.get("kind") or obj.get("format") or fallback_type or "post").lower()
    post_type = "carrousel" if "carrousel" in raw_type or "carousel" in raw_type else "post"

    title = (
        obj.get("titre")
        or obj.get("title")
        or obj.get("name")
        or fallback_title
        or ("Carrousel planifié" if post_type == "carrousel" else "Post planifié")
    )

    caption = (
        obj.get("caption")
        or obj.get("text")
        or obj.get("texte")
        or obj.get("description")
        or ""
    )

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


def _parse_scheduled_datetime(payload: Dict[str, Any]) -> datetime:
    raw = payload.get("scheduled_at") or payload.get("scheduled_for") or payload.get("date_programmee")

    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass

    date = payload.get("date")
    time_value = payload.get("time")
    if isinstance(date, str) and isinstance(time_value, str) and date.strip() and time_value.strip():
        try:
            return datetime.strptime(f"{date} {time_value}", "%Y-%m-%d %H:%M")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"date/time invalide: {e}")

    raise HTTPException(status_code=400, detail="Date/heure invalide (date_programmee).")


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    content_obj = _content_summary(row.get("contenu"), fallback_title=row.get("titre"))
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
        "media_url": None,
        "published_at": row.get("published_at").isoformat() if hasattr(row.get("published_at"), "isoformat") else row.get("published_at"),
        "supprimer_apres": bool(row.get("supprimer_apres", False)),
        "created_at": row.get("created_at").isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
        "updated_at": row.get("updated_at").isoformat() if hasattr(row.get("updated_at"), "isoformat") else row.get("updated_at"),
    }


def _require_future(dt: datetime) -> None:
    if dt <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="La date de publication doit être dans le futur")


def _insert_social_post(
    db: Session,
    *,
    user_id: int,
    reseau: str,
    contenu_obj: Dict[str, Any],
    date_programmee: datetime,
    supprimer_apres: bool,
) -> Dict[str, Any]:
    safe_content = _content_summary(contenu_obj, fallback_type=str(contenu_obj.get("type") or "post"))

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
            "user_id": int(user_id),
            "reseau": str(reseau),
            "statut": "scheduled",
            "contenu": json.dumps(safe_content, ensure_ascii=False),
            "date_programmee": date_programmee,
            "supprimer_apres": bool(supprimer_apres),
        },
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=500, detail="Insertion planner impossible")

    db.commit()
    return dict(row)


@router.get("/posts")
def list_planner_posts(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[Dict[str, Any]]:
    # Critical: never load full heavy 'contenu' from older rows.
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
        rows = db.execute(sql, {"user_id": _user_id(user)}).mappings().all()
        return [_serialize_row(dict(r)) for r in rows]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"planner posts failed: {e}")


@router.post("/schedule-post")
def schedule_post(payload: Dict[str, Any], db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        network = _normalize_network(payload.get("network") or payload.get("reseau"))
        if network not in ALLOWED_NETWORKS:
            raise HTTPException(status_code=400, detail=f"network invalide: {network}")

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        content_obj = payload.get("contenu") or payload.get("content") or {}
        if not isinstance(content_obj, dict):
            content_obj = {"text": str(content_obj or "")}

        for k in ("titre", "title", "text", "caption", "format"):
            if payload.get(k) is not None and k not in content_obj:
                content_obj[k] = payload.get(k)

        content_obj["type"] = "post"

        row = _insert_social_post(
            db,
            user_id=_user_id(user),
            reseau=network,
            contenu_obj=content_obj,
            date_programmee=dt,
            supprimer_apres=bool(payload.get("supprimer_apres", False)),
        )

        return {
            "ok": True,
            "id": row["id"],
            "statut": row["statut"],
            "date_programmee": row["date_programmee"].isoformat() if row.get("date_programmee") else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"schedule-post failed: {e}")


@router.post("/schedule-carrousel")
def schedule_carrousel(payload: Dict[str, Any], db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        network = _normalize_network(payload.get("network") or payload.get("reseau"))
        if network not in ALLOWED_NETWORKS:
            raise HTTPException(status_code=400, detail=f"network invalide: {network}")

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        content_obj = payload.get("contenu") or payload.get("content") or {}
        if not isinstance(content_obj, dict):
            content_obj = {}

        content_obj["type"] = "carrousel"
        if payload.get("slides") is not None:
            content_obj["slides"] = payload.get("slides")
        if payload.get("titre") and "title" not in content_obj:
            content_obj["title"] = payload.get("titre")

        row = _insert_social_post(
            db,
            user_id=_user_id(user),
            reseau=network,
            contenu_obj=content_obj,
            date_programmee=dt,
            supprimer_apres=bool(payload.get("supprimer_apres", False)),
        )

        return {
            "ok": True,
            "id": row["id"],
            "statut": row["statut"],
            "date_programmee": row["date_programmee"].isoformat() if row.get("date_programmee") else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"schedule-carrousel failed: {e}")


@router.post("/schedule")
def schedule_legacy_alias(payload: Dict[str, Any], db: Session = Depends(get_db), user=Depends(get_current_user)):
    content = payload.get("contenu") or payload.get("content") or {}
    if payload.get("slides") or (isinstance(content, dict) and content.get("slides")):
        return schedule_carrousel(payload=payload, db=db, user=user)
    return schedule_post(payload=payload, db=db, user=user)


@router.patch("/posts/{post_id}/manual-status")
def update_manual_post_status(post_id: int, payload: Dict[str, Any], db: Session = Depends(get_db), user=Depends(get_current_user)):
    status = str(payload.get("status") or payload.get("statut") or "").strip().lower()
    if status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="status invalide")

    published_at_value = "NOW()" if status == "published" else "NULL"

    sql = text(
        f"""
        UPDATE social_posts
        SET statut = :status,
            published_at = {published_at_value},
            updated_at = NOW()
        WHERE id = :post_id AND user_id = :user_id
        RETURNING id, user_id, reseau, statut,
                  SUBSTRING(contenu FROM 1 FOR 6000) AS contenu,
                  date_programmee, published_at, supprimer_apres, created_at, updated_at
        """
    )

    row = db.execute(sql, {"status": status, "post_id": int(post_id), "user_id": _user_id(user)}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Post introuvable")

    db.commit()
    return {"ok": True, "post": _serialize_row(dict(row))}


@router.delete("/posts/{post_id}")
def delete_planner_post(post_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sql = text(
        """
        DELETE FROM social_posts
        WHERE id = :post_id AND user_id = :user_id
        RETURNING id
        """
    )
    row = db.execute(sql, {"post_id": int(post_id), "user_id": _user_id(user)}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Post introuvable")

    db.commit()
    return {"ok": True, "deleted_id": int(row["id"])}
