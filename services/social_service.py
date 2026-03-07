from sqlalchemy.orm import Session
from datetime import datetime

from models.social_post_model import SocialPost
from models.social_post_log import SocialPostLog
from schemas.social_post_schema import (
    SocialPostCreateSchema,
    SocialPostUpdateSchema
)


# ============================================================
# 📌 CREATION
# ============================================================

def create_social_post(db: Session, user_id: int, payload: SocialPostCreateSchema):
    post = SocialPost(
        user_id=user_id,
        titre=payload.titre,
        reseau=payload.reseau,
        format=payload.format,
        contenu=payload.contenu,
        date_programmee=payload.date_programmee,
        archive=payload.archive,
        supprimer_apres=payload.supprimer_apres,
    )

    db.add(post)
    db.commit()
    db.refresh(post)
    return post


# ============================================================
# ✏ UPDATE
# ============================================================

def update_social_post(db: Session, post: SocialPost, payload: SocialPostUpdateSchema):
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(post, field, value)

    db.commit()
    db.refresh(post)
    return post


# ============================================================
# ❌ DELETE
# ============================================================

def delete_social_post(db: Session, post: SocialPost):
    db.delete(post)
    db.commit()


# ============================================================
# 📘 LOGS
# ============================================================

def add_log(db: Session, post_id: int, status: str, message: str):
    log = SocialPostLog(
        post_id=post_id,
        status=status,
        message=message
    )
    db.add(log)
    db.commit()
    return log
