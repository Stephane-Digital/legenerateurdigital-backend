# =========================================================
#  LGD — ROUTES CARROUSEL (Backend)
#  Version 2025 — Alignée option A (bulk slides)
# =========================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models.user_model import User
from models.carrousel_model import Carrousel
from models.carrousel_slide_model import CarrouselSlide
from routes.auth import get_current_user

router = APIRouter(prefix="/carrousel", tags=["Carrousel"])


# =========================================================
# 🟦 1. GET — Liste des carrousels du user (AJOUT LGD)
# =========================================================
@router.get("/", response_model=List[dict])
def get_user_carrousels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retourne tous les carrousels appartenant à l'utilisateur connecté.
    """
    carrousels = (
        db.query(Carrousel)
        .filter(Carrousel.user_id == current_user.id)
        .order_by(Carrousel.id.desc())
        .all()
    )

    results = []
    for c in carrousels:
        results.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
        })

    return results


# =========================================================
# 🟦 2. POST — Créer un carrousel vide
# =========================================================
@router.post("/")
def create_carrousel(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    title = payload.get("title", "Nouveau carrousel")
    description = payload.get("description", "")

    carrousel = Carrousel(
        title=title,
        description=description,
        user_id=current_user.id
    )
    db.add(carrousel)
    db.commit()
    db.refresh(carrousel)

    # créer une slide vide par défaut
    default_slide = CarrouselSlide(
        carrousel_id=carrousel.id,
        position=0,
        title="Slide 1",
        json_layers="[]"
    )
    db.add(default_slide)
    db.commit()

    return {
        "id": carrousel.id,
        "title": carrousel.title,
        "description": carrousel.description,
    }


# =========================================================
# 🟦 3. GET — Charger un carrousel (avec toutes ses slides)
# =========================================================
@router.get("/{carrousel_id}")
def get_carrousel(
    carrousel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    carrousel = db.query(Carrousel).filter(
        Carrousel.id == carrousel_id,
        Carrousel.user_id == current_user.id
    ).first()

    if not carrousel:
        raise HTTPException(status_code=404, detail="Carrousel introuvable")

    slides = (
        db.query(CarrouselSlide)
        .filter(CarrouselSlide.carrousel_id == carrousel.id)
        .order_by(CarrouselSlide.position)
        .all()
    )

    return {
        "id": carrousel.id,
        "title": carrousel.title,
        "description": carrousel.description,
        "slides": [
            {
                "id": s.id,
                "position": s.position,
                "title": s.title,
                "json_layers": s.json_layers,
                "thumbnail_url": s.thumbnail_url,
            }
            for s in slides
        ],
    }


# =========================================================
# 🟦 4. PUT — Mise à jour COMPLETE du carrousel
#        (slides bulk — OPTION A)
# =========================================================
@router.put("/{carrousel_id}")
def update_carrousel(
    carrousel_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # -----------------------------
    # 🔹 Charger le carrousel
    # -----------------------------
    carrousel = db.query(Carrousel).filter(
        Carrousel.id == carrousel_id,
        Carrousel.user_id == current_user.id
    ).first()

    if not carrousel:
        raise HTTPException(status_code=404, detail="Carrousel introuvable")

    # -----------------------------
    # 🔹 Mettre à jour title/description
    # -----------------------------
    carrousel.title = payload.get("title", carrousel.title)
    carrousel.description = payload.get("description", carrousel.description)
    db.commit()

    # -----------------------------
    # 🔥 Bulk update des slides
    # -----------------------------
    slides_payload = payload.get("slides", [])

    for s in slides_payload:
        slide = db.query(CarrouselSlide).filter(
            CarrouselSlide.id == s["id"],
            CarrouselSlide.carrousel_id == carrousel.id
        ).first()

        if slide:
            slide.position = s.get("position", slide.position)
            slide.title = s.get("title", slide.title)
            slide.json_layers = s.get("json_layers", slide.json_layers)

    db.commit()

    return {"status": "updated"}


# =========================================================
# 🟦 5. DELETE — Supprimer un carrousel
# =========================================================
@router.delete("/{carrousel_id}")
def delete_carrousel(
    carrousel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    carrousel = db.query(Carrousel).filter(
        Carrousel.id == carrousel_id,
        Carrousel.user_id == current_user.id
    ).first()

    if not carrousel:
        raise HTTPException(status_code=404, detail="Carrousel introuvable")

    # slides supprimées via cascade
    db.delete(carrousel)
    db.commit()

    return {"status": "deleted"}
