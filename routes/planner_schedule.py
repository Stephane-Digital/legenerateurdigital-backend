# C:\LGD\legenerateurdigital_backend\routes\planner_schedule.py
"""
LGD — Planner Scheduling (DB-safe)
- Compatible with current Render DB schema for social_posts
- Avoids ORM insert on columns that don't exist yet in production
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
    raw = payload.get("scheduled_at") or payload.get("scheduled_for") or payload.get("date_programmee")
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

    raise HTTPException(status_code=400, detail="Date/heure invalide (date_programmee).")


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    content_obj = _safe_json_loads(row.get("contenu"))
    date_prog = row.get("date_programmee")
    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "reseau": row.get("reseau"),
        "network": row.get("reseau"),
        "statut": row.get("statut"),
        "status": row.get("statut"),
        "titre": _extract_title(content_obj),
        "title": _extract_title(content_obj),
        "format": _extract_format(content_obj),
        "contenu": content_obj,
        "date_programmee": date_prog,
        "scheduled_at": date_prog,
        "scheduled_for": date_prog,
        "media_url": _extract_media_url(content_obj),
        "supprimer_apres": bool(row.get("supprimer_apres", False)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
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
    sql = text(
        """
        INSERT INTO social_posts
            (user_id, reseau, statut, contenu, date_programmee, supprimer_apres, created_at, updated_at)
        VALUES
            (:user_id, :reseau, :statut, :contenu, :date_programmee, :supprimer_apres, NOW(), NOW())
        RETURNING id, user_id, reseau, statut, contenu, date_programmee, supprimer_apres, created_at, updated_at
        """
    )

    row = db.execute(
        sql,
        {
            "user_id": int(user_id),
            "reseau": str(reseau),
            "statut": "scheduled",
            "contenu": json.dumps(contenu_obj, ensure_ascii=False),
            "date_programmee": date_programmee,
            "supprimer_apres": bool(supprimer_apres),
        },
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=500, detail="Insertion planner impossible")

    db.commit()
    return dict(row)


@router.get("/posts", response_model=List[Dict[str, Any]])
def list_planner_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text(
        """
        SELECT id, user_id, reseau, statut, contenu, date_programmee, supprimer_apres, created_at, updated_at
        FROM social_posts
        WHERE user_id = :user_id
        ORDER BY date_programmee DESC, id DESC
        """
    )
    rows = db.execute(sql, {"user_id": _user_id(user)}).mappings().all()
    return [_serialize_row(dict(r)) for r in rows]


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
            # fallback: keep the whole payload UI content when front sends only top-level fields
            content_obj = payload.get("content") or {}

        if isinstance(content_obj, str):
            content_obj = _safe_json_loads(content_obj)
            if isinstance(content_obj, str):
                content_obj = {"text": content_obj}

        if not isinstance(content_obj, dict):
            content_obj = {"value": content_obj}

        for k in ("titre", "title", "text", "caption", "format", "image_url", "media_url", "ui"):
            if payload.get(k) is not None and k not in content_obj:
                content_obj[k] = payload.get(k)

        if "type" not in content_obj:
            content_obj["type"] = content_obj.get("kind") or payload.get("format") or "post"

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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule")
def schedule_legacy_alias(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return schedule_carrousel(payload=payload, db=db, user=user)
