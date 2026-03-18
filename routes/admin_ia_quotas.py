from __future__ import annotations


import os
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

# IMPORTANT: do NOT import db.session at module import time (it can break env loading).
# We import get_db lazily to avoid startup crashes if the project structure differs.
def _get_db_dep():
    for mod, name in (
        ("db.session", "get_db"),
        ("db", "get_db"),
        ("database", "get_db"),
        ("core.database", "get_db"),
    ):
        try:
            m = __import__(mod, fromlist=[name])
            return getattr(m, name)
        except Exception:
            continue
    raise RuntimeError("get_db dependency not found (expected db.session.get_db or db.get_db)")


get_db = _get_db_dep()

from services.ia_quota_admin import list_quotas, reset_quota, set_quota_limit, plan_default_limit
from services.user_entitlements import set_plan_override, clear_plan_override

# ✅ We also update the quota row so plan+limit stay coherent across reload.
from services.ai_quota_service import get_or_create_quota

router = APIRouter(prefix="/admin/ia", tags=["admin-ia"])


def _require_admin_key(admin_key: Optional[str]) -> None:
    if not admin_key or not str(admin_key).strip():
        raise HTTPException(status_code=401, detail="ADMIN KEY manquant côté backend (.env)")


def _pick_admin_key(admin_key_q: str | None, payload: dict | None) -> str:
    if payload and isinstance(payload, dict):
        k = payload.get("admin_key")
        if isinstance(k, str) and k.strip():
            return k.strip()
    if isinstance(admin_key_q, str) and admin_key_q.strip():
        return admin_key_q.strip()
    return ""


def _safe_set_attr(obj: Any, name: str, value: Any) -> bool:
    try:
        if hasattr(obj, name):
            setattr(obj, name, value)
            return True
    except Exception:
        pass
    return False


def _compute_default_limit(plan: str, feature: str | None) -> int:
    """Call plan_default_limit defensively (signature differs across versions)."""
    try:
        return int(plan_default_limit(plan, feature))
    except TypeError:
        pass
    try:
        return int(plan_default_limit(plan=plan, feature=feature))
    except TypeError:
        pass
    try:
        return int(plan_default_limit(plan))
    except Exception:
        return 0


class PlanOverrideBody(BaseModel):
    plan: str
    months: int = 3
    note: Optional[str] = None


class QuotaLimitBody(BaseModel):
    user_id: int
    feature: Optional[str] = None
    limit_tokens: int


@router.get("/quotas")
def get_quotas(
    admin_key: str = Query(...),
    feature: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(10),
    db: Session = Depends(get_db),
) -> Any:
    _require_admin_key(admin_key)
    return list_quotas(db=db, feature=feature, plan=plan, q=q, page=page, page_size=page_size)


@router.post("/quotas/reset")
def post_reset_quota(
    payload: dict | None = Body(None),
    plan: str | None = Query(None),
    months: int | None = Query(None),
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
) -> Any:
    _require_admin_key(admin_key)
    payload = payload or {}
    user_id = payload.get("user_id")
    feature = payload.get("feature")
    try:
        return reset_quota(db=db, user_id=int(user_id), feature=feature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quotas/set-limit")
def post_set_limit(
    payload: dict | None = Body(None),
    plan: str | None = Query(None),
    months: int | None = Query(None),
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
) -> Any:
    _require_admin_key(admin_key)
    payload = payload or {}
    try:
        user_id = int(payload.get("user_id"))
        limit_tokens = int(payload.get("limit_tokens"))
        feature = payload.get("feature")
        return set_quota_limit(db=db, user_id=user_id, limit_tokens=limit_tokens, feature=feature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Buttons: "Pro 3 mois" / "Ultime 3 mois"
@router.post("/users/{user_id}/plan-override")
def post_plan_override(
    user_id: int,
    payload: dict | None = Body(None),
    plan: str | None = Query(None),
    months: int | None = Query(None),
    admin_key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    payload = payload or {}
    key = _pick_admin_key(admin_key, payload)
    _require_admin_key(key)

    plan_val = payload.get("plan") or plan
    months_val = payload.get("months") or payload.get("duration_months") or months or 3
    months_val = int(months_val or 3)
    if not plan_val:
        raise HTTPException(status_code=422, detail="plan manquant")

    feature = payload.get("feature") or "coach"
    note = payload.get("note")

    # 1) Persist entitlements override (SOURCE OF TRUTH for admin listing)
    try:
        ent = set_plan_override(
            db,
            user_id=int(user_id),
            plan=str(plan_val),
            months=months_val,
            note=note,
            created_by="admin",
        )
        # ✅ Force commit here so a later failure cannot rollback the plan override
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2) Best-effort align quota row plan+limit (does NOT block the request)
    try:
        with db.begin_nested():
            quota = get_or_create_quota(db, int(user_id))

            _safe_set_attr(quota, "plan", str(plan_val).lower())
            _safe_set_attr(quota, "feature", str(feature))

            default_limit = _compute_default_limit(str(plan_val).lower(), str(feature))
            if default_limit:
                _safe_set_attr(quota, "limit_tokens", int(default_limit))
                _safe_set_attr(quota, "tokens_limit", int(default_limit))
        db.commit()
    except Exception:
        # Do NOT rollback the outer transaction (override is already committed).
        # Only ignore this alignment step.
        try:
            db.rollback()
        except Exception:
            pass

    return {"ok": True, "entitlement": ent}


@router.post("/users/{user_id}/plan-clear")
def post_plan_clear(
    user_id: int,
    payload: dict | None = Body(None),
    admin_key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    payload = payload or {}
    key = _pick_admin_key(admin_key, payload)
    _require_admin_key(key)

    feature = payload.get("feature") or "coach"

    # 1) Clear entitlement override and commit (SOURCE OF TRUTH for admin listing)
    out = clear_plan_override(db, user_id=int(user_id))
    try:
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # 2) Best-effort align quota row back to Essentiel defaults
    try:
        with db.begin_nested():
            quota = get_or_create_quota(db, int(user_id))
            _safe_set_attr(quota, "plan", "essentiel")
            _safe_set_attr(quota, "feature", str(feature))

            default_limit = _compute_default_limit("essentiel", str(feature))
            if default_limit:
                _safe_set_attr(quota, "limit_tokens", int(default_limit))
                _safe_set_attr(quota, "tokens_limit", int(default_limit))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return {"ok": True, "cleared": out}


@router.post("/users/{user_id}/quota/reset")
def post_user_quota_reset(
    user_id: int,
    payload: dict | None = Body(None),
    admin_key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    payload = payload or {}
    key = _pick_admin_key(admin_key, payload)
    _require_admin_key(key)
    feature = payload.get("feature")
    try:
        return reset_quota(db=db, user_id=int(user_id), feature=feature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/quota/limit")
def post_user_quota_limit(
    user_id: int,
    payload: dict | None = Body(None),
    plan: str | None = Query(None),
    months: int | None = Query(None),
    admin_key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    payload = payload or {}
    key = _pick_admin_key(admin_key, payload)
    _require_admin_key(key)
    feature = payload.get("feature")
    try:
        limit_tokens = int(payload.get("limit_tokens"))
        return set_quota_limit(db=db, user_id=int(user_id), limit_tokens=limit_tokens, feature=feature)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
