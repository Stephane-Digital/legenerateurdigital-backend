from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from schemas.coach_profile_schema import CoachProfileOut, CoachProfileReplaceIn, CoachProfileUpdateIn
from services.coach_profile_service import read_profile, write_profile_patch, write_profile_replace

try:
    from services.coach_profile_service import patch_business_project
except Exception:  # pragma: no cover - compat prod si service non encore mis à jour
    patch_business_project = None  # type: ignore

# --- deps: get_db + current user ---
try:
    from db import get_db  # type: ignore
except Exception:
    from database import get_db  # type: ignore

# Auth dependency (robust import)
get_current_user = None
for _path in (
    "auth",
    "routes.auth",
    "routes.auth_routes",
    "routes.auth_user",
    "utils.auth",
    "dependencies.auth",
):
    try:
        mod = __import__(_path, fromlist=["get_current_user"])
        get_current_user = getattr(mod, "get_current_user")
        break
    except Exception:
        continue

if get_current_user is None:
    # last resort: import from routes/auth.py typical LGD
    try:
        from routes.auth import get_current_user  # type: ignore
    except Exception:
        get_current_user = None

router = APIRouter(prefix="/coach-profile", tags=["CoachProfile"])


class CoachBusinessProjectPatchIn(BaseModel):
    """
    Patch dédié au futur moteur FormAction.
    Tous les champs sont optionnels pour permettre des sauvegardes progressives.
    """
    project_type: Optional[str] = None
    business_mode: Optional[str] = None
    project_status: Optional[str] = None
    project_label: Optional[str] = None
    project_name: Optional[str] = None
    offer_name: Optional[str] = None
    niche: Optional[str] = None
    audience: Optional[str] = None
    pain: Optional[str] = None
    promise: Optional[str] = None
    product_type: Optional[str] = None
    price: Optional[str] = None
    recommended_platform: Optional[str] = None
    estimated_days_to_launch: Optional[int] = Field(default=None, ge=0)
    current_step: Optional[str] = None
    next_action: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


def _user_id_from_user(u) -> int:
    # LGD: user may be Pydantic model or SQLAlchemy model
    if hasattr(u, "id"):
        return int(getattr(u, "id"))
    if isinstance(u, dict) and "id" in u:
        return int(u["id"])
    raise HTTPException(status_code=401, detail="Utilisateur non authentifié")


def _clean_project_patch(payload: CoachBusinessProjectPatchIn) -> Dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    extra = data.pop("extra", None)

    if isinstance(extra, dict):
        data.update(extra)

    return data


def _fallback_patch_business_project(db: Session, user_id: int, patch: Dict[str, Any]):
    """
    Sécurité si le service dédié n'est pas encore déployé.
    On reste compatible avec write_profile_patch existant.
    """
    current = read_profile(db, user_id)
    existing = current.get("alex_business_project")
    if not isinstance(existing, dict):
        existing = {}

    merged = {
        **existing,
        **patch,
        "source": patch.get("source") or existing.get("source") or "coach_profile_route",
    }

    return write_profile_patch(db, user_id, patch={"alex_business_project": merged})



@router.get("/business-project")
def get_my_business_project(db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore
    """
    LGD — Coach Alex FormAction
    Retourne la mémoire projet business de l'utilisateur.
    """
    if get_current_user is None:
        raise HTTPException(status_code=500, detail="Auth dependency get_current_user introuvable")

    user_id = _user_id_from_user(user)
    profile = read_profile(db, user_id)
    project = profile.get("alex_business_project") or {}

    return {
        "user_id": user_id,
        "alex_business_project": project if isinstance(project, dict) else {},
    }


@router.patch("/business-project")
def patch_my_business_project(payload: CoachBusinessProjectPatchIn, db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore
    """
    LGD — Coach Alex FormAction
    Sauvegarde progressive du projet business : produit digital, affiliation, ebook, plateforme, étape, mission suivante.
    """
    if get_current_user is None:
        raise HTTPException(status_code=500, detail="Auth dependency get_current_user introuvable")

    user_id = _user_id_from_user(user)
    patch = _clean_project_patch(payload)

    if patch_business_project is not None:
        patch_business_project(db, user_id, patch=patch)  # type: ignore
    else:
        _fallback_patch_business_project(db, user_id, patch)

    profile = read_profile(db, user_id)
    project = profile.get("alex_business_project") or {}

    return {
        "user_id": user_id,
        "alex_business_project": project if isinstance(project, dict) else {},
    }


@router.get("", response_model=CoachProfileOut)
def get_my_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore
    if get_current_user is None:
        raise HTTPException(status_code=500, detail="Auth dependency get_current_user introuvable")

    user_id = _user_id_from_user(user)
    profile = read_profile(db, user_id)

    # convenience fields (stored in model) are fetched by service replace/patch; here we just return from blob.
    # If you want strictness, keep intent/level/time_per_day duplicated.
    return CoachProfileOut(user_id=user_id, profile=profile, intent=profile.get("intent"), level=profile.get("level"), time_per_day=profile.get("time_per_day"))


@router.put("", response_model=CoachProfileOut)
def replace_my_profile(payload: CoachProfileReplaceIn, db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore
    if get_current_user is None:
        raise HTTPException(status_code=500, detail="Auth dependency get_current_user introuvable")

    user_id = _user_id_from_user(user)

    # mirror convenience fields into the profile blob
    profile = dict(payload.profile or {})
    if payload.intent is not None:
        profile["intent"] = payload.intent
    if payload.level is not None:
        profile["level"] = payload.level
    if payload.time_per_day is not None:
        profile["time_per_day"] = payload.time_per_day

    cp = write_profile_replace(
        db,
        user_id,
        profile=profile,
        intent=payload.intent,
        level=payload.level,
        time_per_day=payload.time_per_day,
    )

    out_profile = read_profile(db, user_id)
    return CoachProfileOut(user_id=user_id, profile=out_profile, intent=cp.intent, level=cp.level, time_per_day=cp.time_per_day)


@router.patch("", response_model=CoachProfileOut)
def patch_my_profile(payload: CoachProfileUpdateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore
    if get_current_user is None:
        raise HTTPException(status_code=500, detail="Auth dependency get_current_user introuvable")

    user_id = _user_id_from_user(user)

    patch = payload.profile or {}
    if payload.intent is not None:
        patch["intent"] = payload.intent
    if payload.level is not None:
        patch["level"] = payload.level
    if payload.time_per_day is not None:
        patch["time_per_day"] = payload.time_per_day

    cp = write_profile_patch(
        db,
        user_id,
        patch=patch,
        intent=payload.intent,
        level=payload.level,
        time_per_day=payload.time_per_day,
    )

    out_profile = read_profile(db, user_id)
    return CoachProfileOut(user_id=user_id, profile=out_profile, intent=cp.intent, level=cp.level, time_per_day=cp.time_per_day)
