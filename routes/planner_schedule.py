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

IMPORTANT:
- On utilise le modèle "SocialPost" (models.social_post_model) qui stocke:
  - reseau (network)
  - contenu (JSON string)
  - date_programmee (datetime)
  - statut (draft/scheduled/published/error)
  - supprimer_apres (bool)
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


# ============================================================
# Helpers
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


def _parse_scheduled_datetime(payload: Dict[str, Any]) -> datetime:
    """
    Accepts multiple formats:
    - scheduled_at: ISO string (preferred)
    - date + time: "YYYY-MM-DD" + "HH:MM"
    """
    # A) ISO (scheduled_at / scheduled_for)
    for key in ("scheduled_at", "scheduled_for", "date_programmee"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                # supports "2026-03-01T12:34:00" and with timezone
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

    # B) date + time
    date = payload.get("date")
    time = payload.get("time")
    if isinstance(date, str) and isinstance(time, str) and date.strip() and time.strip():
        try:
            dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            return dt
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
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
    }


def _require_future(dt: datetime) -> None:
    # use naive utcnow for consistency with existing codebase
    if dt <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="La date de publication doit être dans le futur")


# ============================================================
# ✅ LIST POSTS (Front expects /planner/posts)
# ============================================================

@router.get("/posts", response_model=List[Dict[str, Any]])
def list_planner_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.user_id == user.id)
        .order_by(SocialPost.date_programmee.desc())
        .all()
    )
    return [_serialize_post(p) for p in posts]


# ============================================================
# ✅ SCHEDULE POST (Editor Intelligent -> Planner)
# ============================================================

@router.post("/schedule-post")
def schedule_post(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Payload attendu (tolérant):
    - network: "facebook" | "instagram" | "pinterest" | ...
    - scheduled_at (ISO) OR date + time
    - contenu: object|string (optionnel)  -> stocké dans SocialPost.contenu
      ou fields à plat (title/titre/text/caption/format/...)
    - supprimer_apres: bool (optionnel)
    """
    try:
        network = str(payload.get("network") or payload.get("reseau") or "").strip().lower()
        if not network:
            raise HTTPException(status_code=400, detail="network manquant")

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        # Normalisation contenu
        content_obj: Any = payload.get("contenu")
        if content_obj is None:
            content_obj = {}

        if isinstance(content_obj, str):
            content_obj = _safe_json_loads(content_obj)
            if isinstance(content_obj, str):
                content_obj = {"text": content_obj}

        if not isinstance(content_obj, dict):
            content_obj = {"value": content_obj}

        # inject fields à plat si fournis
        for k in ("titre", "title", "text", "caption", "format"):
            if payload.get(k) is not None and k not in content_obj:
                content_obj[k] = payload.get(k)

        # marqueur type
        if "type" not in content_obj:
            content_obj["type"] = content_obj.get("kind") or "post"

        post = SocialPost(
            user_id=user.id,
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


# ============================================================
# ✅ SCHEDULE CARROUSEL (Editor Intelligent -> Planner)
# ============================================================

@router.post("/schedule-carrousel")
def schedule_carrousel(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Payload attendu (tolérant):
    - network
    - carrousel_id
    - slides (array)
    - scheduled_at (ISO) OR date + time
    - supprimer_apres (optionnel)
    """
    try:
        network = str(payload.get("network") or payload.get("reseau") or "").strip().lower()
        if not network:
            raise HTTPException(status_code=400, detail="network manquant")

        carrousel_id = payload.get("carrousel_id") or payload.get("carousel_id")
        slides = payload.get("slides")
        if slides is None or (isinstance(slides, list) and len(slides) == 0):
            raise HTTPException(status_code=400, detail="slides manquant (array)")

        # carrousel_id peut être null côté front (ex: carrousel non encore persisté)
        # On l'accepte et on stocke tout dans `contenu` pour préserver la planification.

        dt = _parse_scheduled_datetime(payload)
        _require_future(dt)

        base_contenu = payload.get("contenu")
        if not isinstance(base_contenu, dict):
            base_contenu = {}

        # compat: titre envoyé à plat par certains fronts
        if isinstance(payload.get("titre"), str) and payload.get("titre").strip():
            base_contenu.setdefault("titre", payload.get("titre").strip())

        contenu = {
            **base_contenu,
            "type": "carrousel",
            "slides": slides,
        }
        if carrousel_id is not None:
            contenu["carrousel_id"] = carrousel_id

        post = SocialPost(
            user_id=user.id,
            reseau=network,
            statut="scheduled",
            contenu=json.dumps(contenu, ensure_ascii=False),
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


# ============================================================
# ♻️ Backward-compat alias
# ============================================================

@router.post("/schedule")
def schedule_carrousel_legacy(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Ancien endpoint conservé (alias de /schedule-carrousel).
    """
    return schedule_carrousel(payload=payload, db=db, user=user)
