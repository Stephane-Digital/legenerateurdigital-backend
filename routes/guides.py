from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database import get_db
from services.auth_service import get_current_user
from models.guide_model import Guide

router = APIRouter(prefix="/guides", tags=["Guides"])


# ============================================================
# 📌 SCHEMAS LOCAUX
# ============================================================

class GuideBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None


class GuideCreate(GuideBase):
    pass


class GuideUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


class GuideOut(GuideBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 📜 LISTE
# ============================================================

@router.get("/", response_model=List[GuideOut])
def list_guides(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    guides = (
        db.query(Guide)
        .filter(Guide.user_id == user.id)
        .order_by(Guide.created_at.desc())
        .all()
    )
    return guides


# ============================================================
# ➕ CRÉATION
# ============================================================

@router.post("/", response_model=GuideOut)
def create_guide(
    payload: GuideCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    guide = Guide(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


# ============================================================
# 🔎 GET ONE
# ============================================================

@router.get("/{guide_id}", response_model=GuideOut)
def get_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    guide = (
        db.query(Guide)
        .filter(
            Guide.id == guide_id,
            Guide.user_id == user.id,
        )
        .first()
    )
    if not guide:
        raise HTTPException(status_code=404, detail="Guide introuvable")
    return guide


# ============================================================
# ✏️ UPDATE
# ============================================================

@router.put("/{guide_id}", response_model=GuideOut)
def update_guide(
    guide_id: int,
    payload: GuideUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    guide = (
        db.query(Guide)
        .filter(
            Guide.id == guide_id,
            Guide.user_id == user.id,
        )
        .first()
    )
    if not guide:
        raise HTTPException(status_code=404, detail="Guide introuvable")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(guide, field, value)

    db.commit()
    db.refresh(guide)
    return guide


# ============================================================
# 🗑 DELETE
# ============================================================

@router.delete("/{guide_id}")
def delete_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    guide = (
        db.query(Guide)
        .filter(
            Guide.id == guide_id,
            Guide.user_id == user.id,
        )
        .first()
    )
    if not guide:
        raise HTTPException(status_code=404, detail="Guide introuvable")

    db.delete(guide)
    db.commit()
    return {"status": "deleted"}
