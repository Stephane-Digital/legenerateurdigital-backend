# legenerateurdigital_backend/routes/social_posts.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db

# ✅ IMPORTANT: dans ton codebase tu as parfois routes.auth et parfois services.auth_service
try:
    from routes.auth import get_current_user
except Exception:  # pragma: no cover
    from services.auth_service import get_current_user  # type: ignore

try:
    from models.social_post_model import SocialPost
except Exception:  # pragma: no cover
    from models.social_post import SocialPost  # type: ignore

from schemas.social_post_schema import SocialPostCreateSchema, SocialPostResponseSchema

router = APIRouter(prefix="/social-posts", tags=["Social Posts"])


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


def _serialize_post(post: SocialPost) -> Dict[str, Any]:
    # contenu est stocké en JSON string dans la DB (Text)
    content_obj = _safe_json_loads(getattr(post, "contenu", None))

    title = _extract_title(content_obj)
    fmt = _extract_format(content_obj)

    # ✅ compat "network" attendu par certains fronts
    reseau = getattr(post, "reseau", None)

    # ✅ compat dates: certains fronts attendent scheduled_at / scheduled_for
    date_prog = getattr(post, "date_programmee", None)

    return {
        "id": post.id,
        "user_id": post.user_id,
        "reseau": reseau,
        "network": reseau,
        "statut": getattr(post, "statut", None),
        "titre": title,
        "title": title,
        "format": fmt,
        "contenu": content_obj,
        "date_programmee": date_prog,
        "scheduled_at": date_prog,
        "scheduled_for": date_prog,
        "supprimer_apres": bool(getattr(post, "supprimer_apres", False)),
    }


# ✅ Évite le 307 redirect /social-posts -> /social-posts/
@router.get("", response_model=List[SocialPostResponseSchema])
@router.get("/", response_model=List[SocialPostResponseSchema])
def list_social_posts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.user_id == user.id)
        .order_by(SocialPost.date_programmee.desc())
        .all()
    )
    return [_serialize_post(p) for p in posts]


# ✅ Évite le 307 redirect /social-posts -> /social-posts/
@router.post("", response_model=SocialPostResponseSchema)
@router.post("/", response_model=SocialPostResponseSchema)
def create_social_post(payload: SocialPostCreateSchema, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Création brute d'un SocialPost (utilisée par certaines parties du front).
    ⚠️ Le modèle officiel (social_post_model.py) n'a PAS 'titre' ni 'format'.
    On stocke tout dans 'contenu' (JSON string) mais on renvoie aussi titre/format/network en compat.
    """
    try:
        reseau = (payload.reseau or "").strip().lower()

        content_obj: Any = payload.contenu
        if isinstance(content_obj, str):
            content_obj = _safe_json_loads(content_obj)
            if isinstance(content_obj, str):
                content_obj = {"text": content_obj}
        if content_obj is None:
            content_obj = {}

        # ✅ si le front envoie titre/format à plat, on les injecte dans le contenu JSON
        if isinstance(content_obj, dict):
            if payload.titre and "titre" not in content_obj and "title" not in content_obj:
                content_obj["titre"] = payload.titre
            if payload.format and "format" not in content_obj:
                content_obj["format"] = payload.format

        post = SocialPost(
            user_id=user.id,
            reseau=reseau,
            statut=payload.statut or "draft",
            contenu=json.dumps(content_obj, ensure_ascii=False),
            date_programmee=payload.date_programmee,
            supprimer_apres=bool(payload.supprimer_apres),
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
