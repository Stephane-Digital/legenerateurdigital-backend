from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import json

from database import get_db
from routes.auth import get_current_user
from models.social_post_model import SocialPost

router = APIRouter(prefix="/planner", tags=["Planner"])


@router.post("/schedule")
def schedule_carrousel(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        # =========================
        # 🔒 VALIDATION PAYLOAD
        # =========================
        if "network" not in payload:
            raise ValueError("network manquant")

        if "carrousel_id" not in payload or "slides" not in payload:
            raise ValueError("contenu carrousel manquant")

        if "date" not in payload or "time" not in payload:
            raise ValueError("date ou time manquant")

        # =========================
        # 👤 USER ID SAFE (dict OU ORM)
        # =========================
        user_id = user["id"] if isinstance(user, dict) else user.id

        # =========================
        # 🕒 CONSTRUCTION DATETIME
        # =========================
        datetime_str = f"{payload['date']} {payload['time']}"
        date_programmee = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

        # =========================
        # 📦 CONTENU NORMALISÉ
        # =========================
        contenu = {
            "type": "carrousel",
            "carrousel_id": payload["carrousel_id"],
            "slides": payload["slides"],
        }

        # =========================
        # 🧱 CRÉATION SOCIAL POST
        # =========================
        post = SocialPost(
            user_id=user_id,
            reseau=payload["network"],
            statut="scheduled",
            contenu=json.dumps(contenu),
            date_programmee=date_programmee,
            supprimer_apres=payload.get("supprimer_apres", False),
        )

        db.add(post)
        db.commit()
        db.refresh(post)

        return {
            "id": post.id,
            "statut": post.statut,
            "date_programmee": post.date_programmee.isoformat(),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
