# ============================================================
# 🎠 ROUTES — CARROUSEL SLIDES (LGD V5 FINAL)
# ============================================================

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.carrousel_slide_model import CarrouselSlide
from routes.auth import get_current_user
from schemas.carrousel_slide_schema import (
    CarrouselSlideResponse,
    CarrouselSlideUpdateSchema,
)

router = APIRouter(
    prefix="/carrousel/slides",
    tags=["Carrousel Slides"],
)

# ============================================================
# 🔍 GET — récupérer un slide (layers inclus)
# ============================================================

@router.get("/{slide_id}", response_model=CarrouselSlideResponse)
def get_slide(
    slide_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    slide = db.query(CarrouselSlide).filter(
        CarrouselSlide.id == slide_id
    ).first()

    if not slide:
        raise HTTPException(status_code=404, detail="Slide introuvable")

    return {
        "id": slide.id,
        "position": slide.position,
        "json_layers": json.loads(slide.json_layers or "[]"),
    }


# ============================================================
# 💾 PUT — sauvegarde définitive d’un slide (V5)
# ============================================================

@router.put("/{slide_id}", response_model=CarrouselSlideResponse)
def update_slide(
    slide_id: int,
    payload: CarrouselSlideUpdateSchema,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    slide = db.query(CarrouselSlide).filter(
        CarrouselSlide.id == slide_id
    ).first()

    if not slide:
        raise HTTPException(status_code=404, detail="Slide introuvable")

    # 🔒 SOURCE DE VÉRITÉ — V5 LAYERS
    slide.json_layers = json.dumps(payload.json_layers)

    db.add(slide)
    db.commit()
    db.refresh(slide)

    return {
        "id": slide.id,
        "position": slide.position,
        "json_layers": payload.json_layers,
    }
