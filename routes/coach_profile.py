from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.coach_profile_schema import CoachProfileOut, CoachProfileReplaceIn, CoachProfileUpdateIn
from services.coach_profile_service import read_profile, write_profile_patch, write_profile_replace

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


def _user_id_from_user(u) -> int:
    # LGD: user may be Pydantic model or SQLAlchemy model
    if hasattr(u, "id"):
        return int(getattr(u, "id"))
    if isinstance(u, dict) and "id" in u:
        return int(u["id"])
    raise HTTPException(status_code=401, detail="Utilisateur non authentifié")


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
