from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os
from openai import OpenAI

from models.social_post_model import SocialPost
from models.social_post_log import SocialPostLog
from models.user_model import User

from schemas.social_post_schema import (
    SocialPostCreateSchema,
    SocialPostUpdateSchema,
    SocialPostGenerate,
    SocialPostGeneratePro,
)


# ============================================================
# 🚀 IA SIMPLE — Génération d’un post
# ============================================================
def generate_social_post(db: Session, user: User, payload: SocialPostGenerate):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY manquante dans .env")

    client = OpenAI(api_key=api_key)

    prompt = (
        f"Écris un post pour {payload.reseau} sur : {payload.sujet}. "
        f"Style humain, marketing digital, punchy, hashtags pertinents."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=350,
    )

    texte = completion.choices[0].message.content.strip()

    new_post = SocialPost(
        user_id=user.id,
        titre=payload.sujet,
        reseau=payload.reseau,
        contenu=texte,
        statut="draft",
        archive=False,
        created_at=datetime.utcnow(),
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    log = SocialPostLog(
        user_id=user.id,
        post_id=new_post.id,
        action="generated",
        status="success",
        message="Post généré via IA simple"
    )
    db.add(log)
    db.commit()

    return new_post


# ============================================================
# 🚀 IA PRO — Génération 3 variations
# ============================================================
def generate_social_post_pro(db: Session, user: User, payload: SocialPostGeneratePro):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY manquante dans .env")

    client = OpenAI(api_key=api_key)

    def ask(style):
        prompt = (
            f"Génère un post {style} pour {payload.reseau} sur : {payload.sujet}. "
            f"Ton humain, marketing digital, percutant."
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=350,
        )

        return completion.choices[0].message.content.strip()

    return {
        "courte": ask("très court"),
        "standard": ask("standard"),
        "longue": ask("long"),
    }


# ============================================================
# 📌 Récupérer tous les posts du user
# ============================================================
def get_user_posts(db: Session, user: User):
    return (
        db.query(SocialPost)
        .filter(SocialPost.user_id == user.id)
        .order_by(SocialPost.created_at.desc())
        .all()
    )


# ============================================================
# 📅 PLANNER – Posts programmés
# ============================================================
def get_user_planner_posts(db: Session, user: User):
    return (
        db.query(SocialPost)
        .filter(
            SocialPost.user_id == user.id,
            SocialPost.date_programmee != None,
            SocialPost.statut.in_(["planned"])
        )
        .order_by(SocialPost.date_programmee.asc())
        .all()
    )


# ============================================================
# 🔍 GET BY ID — pour l’éditeur
# ============================================================
def get_post_by_id(db: Session, user: User, post_id: int):
    return (
        db.query(SocialPost)
        .filter(
            SocialPost.id == post_id,
            SocialPost.user_id == user.id
        )
        .first()
    )


# ============================================================
# ✏️ UPDATE POST
# ============================================================
def update_post(db: Session, user: User, post_id: int, payload: SocialPostUpdateSchema):
    post = get_post_by_id(db, user, post_id)
    if not post:
        return None

    data = payload.dict(exclude_unset=True)

    if "date_programmee" in data and data["date_programmee"]:
        post.statut = "planned"
        post.archive = False

    for field, value in data.items():
        setattr(post, field, value)

    db.commit()
    db.refresh(post)

    log = SocialPostLog(
        user_id=user.id,
        post_id=post.id,
        action="edited",
        status="success",
        message="Post modifié (IA ou manuel)"
    )
    db.add(log)
    db.commit()

    if post.statut == "planned":
        log2 = SocialPostLog(
            user_id=user.id,
            post_id=post.id,
            action="replanned",
            status="success",
            message="Post archivé reprogrammé"
        )
        db.add(log2)
        db.commit()

    return post


# ============================================================
# ❌ DELETE POST
# ============================================================
def delete_post(db: Session, user: User, post_id: int):
    post = get_post_by_id(db, user, post_id)
    if not post:
        return False

    db.delete(post)
    db.commit()

    log = SocialPostLog(
        user_id=user.id,
        post_id=post_id,
        action="deleted",
        status="success",
        message="Post supprimé"
    )
    db.add(log)
    db.commit()

    return True


# ============================================================
# 🟢 Worker — Marquer un post comme publié & archivé
# ============================================================
def mark_post_as_published(db: Session, post: SocialPost):
    post.statut = "archived"
    post.archive = True
    post.published_at = datetime.now(timezone.utc)
    post.date_programmee = None

    log = SocialPostLog(
        user_id=post.user_id,
        post_id=post.id,
        action="published",
        status="success",
        message="Publication automatique (worker)"
    )

    db.add(log)
    db.commit()
    db.refresh(post)

    return post
