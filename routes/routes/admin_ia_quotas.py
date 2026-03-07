from __future__ import annotations

from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from services.ia_quota_admin_adapter import list_quotas, reset_quota, set_quota_limit
from services.user_entitlements import set_plan_override, clear_plan_override

import os

router = APIRouter(prefix="/admin/ia", tags=["admin-ia"])


def _get_admin_key_env() -> Optional[str]:
    # support multiple env var names (tolerant)
    return (
        os.getenv("LGD_ADMIN_KEY")
        or os.getenv("ADMIN_IA_KEY")
        or os.getenv("ADMIN_KEY")
        or os.getenv("LGD_ADMIN_IA_KEY")
    )


def _require_admin_key(admin_key: Optional[str]) -> None:
    expected = _get_admin_key_env()
    if not expected:
        raise HTTPException(status_code=400, detail="ADMIN KEY manquant côté backend (.env)")
    if not admin_key or admin_key != expected:
        raise HTTPException(status_code=403, detail="ADMIN KEY invalide")


@router.get("/quotas")
def get_quotas(
    admin_key: str = Query(...),
    feature: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(10),
    db: Session = Depends(get_db),
):
    _require_admin_key(admin_key)
    return list_quotas(db=db, feature=feature, plan=plan, q=q, page=page, page_size=page_size)


class SetLimitBody(BaseModel):
    user_id: int = Field(..., ge=1)
    limit_tokens: int = Field(..., ge=1)
    feature: Optional[str] = None


@router.post("/quota/set-limit")
def post_set_limit(
    body: SetLimitBody,
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_admin_key(admin_key)
    try:
        return set_quota_limit(db=db, user_id=body.user_id, limit_tokens=body.limit_tokens, feature=body.feature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ResetBody(BaseModel):
    user_id: int = Field(..., ge=1)
    feature: Optional[str] = None


@router.post("/quota/reset")
def post_reset(
    body: ResetBody,
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_admin_key(admin_key)
    try:
        return reset_quota(db=db, user_id=body.user_id, feature=body.feature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class PlanOverrideBody(BaseModel):
    plan: str = Field(..., min_length=2)
    months: int = Field(3, ge=1, le=24)
    note: Optional[str] = None


@router.post("/users/{user_id}/plan-override")
def post_plan_override(
    user_id: int,
    body: PlanOverrideBody,
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_admin_key(admin_key)
    return set_plan_override(db=db, user_id=user_id, plan=body.plan, months=body.months, note=body.note, created_by="admin")


@router.delete("/users/{user_id}/plan-override")
def delete_plan_override(
    user_id: int,
    admin_key: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_admin_key(admin_key)
    return clear_plan_override(db=db, user_id=user_id)
