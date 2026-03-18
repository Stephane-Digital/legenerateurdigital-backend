# C:\LGD\legenerateurdigital_backend\routes\social_planner.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from services.auth_service import get_current_user

from models.social_post import SocialPost
from models.carrousel_model import Carrousel
from schemas.social_post_schema import (
    SocialPostCreate,
    SocialPostUpdate,
    SocialPostResponse
)

router = APIRouter(
    prefix="/planner",
    tags=["Social Planner"]
)


# ============================================================
# 📌 LISTE DES POSTS PLANIFIÉS DE L'UTILISATEUR
# ============================================================
@router.get("/", response_model=list[SocialPostResponse])
def list_planned_posts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    posts = db.query(SocialPost).filter(
        SocialPost.user_id == user.id
    ).order_by(SocialPost.scheduled_at.asc()).all()

    return posts


# ============================================================
# ➕ AJOUTER UN POST PLANIFIÉ
# ============================================================
@router.post("/", response_model=SocialPostResponse)
def create_planned_post(
    payload: SocialPostCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Vérification carrousel
    if payload.carrousel_id:
        carrousel = db.query(Carrousel).filter(
            Carrousel.id == payload.carrousel_id,
            Carrousel.user_id == user.id
        ).first()

        if not carrousel:
            raise HTTPException(400, "Carrousel introuvable ou non autorisé")

    # Vérifier date future
    if payload.scheduled_at <= datetime.utcnow():
        raise HTTPException(400, "La date de publication doit être dans le futur")

    new_post = SocialPost(
        user_id=user.id,
        platform=payload.platform,
        text=payload.text,
        media_url=payload.media_url,
        carrousel_id=payload.carrousel_id,
        scheduled_at=payload.scheduled_at,
        status="pending"
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return new_post


# ============================================================
# ♻️ METTRE À JOUR UN POST
# ============================================================
@router.put("/{post_id}", response_model=SocialPostResponse)
def update_planned_post(
    post_id: int,
    payload: SocialPostUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    post = db.query(SocialPost).filter(
        SocialPost.id == post_id,
        SocialPost.user_id == user.id
    ).first()

    if not post:
        raise HTTPException(404, "Post introuvable")

    if payload.text is not None:
        post.text = payload.text

    if payload.media_url is not None:
        post.media_url = payload.media_url

    if payload.scheduled_at is not None:
        if payload.scheduled_at <= datetime.utcnow():
            raise HTTPException(400, "La date doit être dans le futur")
        post.scheduled_at = payload.scheduled_at

    if payload.carrousel_id is not None:
        # Vérifier si carrousel appartient à l'utilisateur
        carrousel = db.query(Carrousel).filter(
            Carrousel.id == payload.carrousel_id,
            Carrousel.user_id == user.id
        ).first()

        if not carrousel:
            raise HTTPException(400, "Carrousel non valide pour cet utilisateur")

        post.carrousel_id = payload.carrousel_id

    db.commit()
    db.refresh(post)

    return post


# ============================================================
# ❌ SUPPRIMER UN POST PLANIFIÉ
# ============================================================
@router.delete("/{post_id}")
def delete_planned_post(
    post_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    post = db.query(SocialPost).filter(
        SocialPost.id == post_id,
        SocialPost.user_id == user.id
    ).first()

    if not post:
        raise HTTPException(404, "Post introuvable")

    db.delete(post)
    db.commit()

    return {"message": "Post supprimé avec succès"}
