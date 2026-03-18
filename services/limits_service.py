from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.user_model import User
from enums.plan_enum import UserPlan
from models.ia_status_model import IAStatus


# ================================
# LIMITES PAR PLAN (LGD OFFICIEL)
# ================================

PLAN_LIMITS = {
    UserPlan.ESSENTIAL: {
        "slides_per_carrousel": 5,
        "images_per_slide": 1,
        "ia_background_per_day": 3,
        "ia_templates": False,
        "ia_style_transfer": False,
        "export_png_transparent": False,
        "export_pdf": False,
        "export_mp4": False,
    },
    UserPlan.PRO: {
        "slides_per_carrousel": 10,
        "images_per_slide": 3,
        "ia_background_per_day": 20,
        "ia_templates": True,
        "ia_style_transfer": True,
        "export_png_transparent": True,
        "export_pdf": False,
        "export_mp4": False,
    },
    UserPlan.ULTIMATE: {
        "slides_per_carrousel": 999,
        "images_per_slide": 999,
        "ia_background_per_day": 999,
        "ia_templates": True,
        "ia_style_transfer": True,
        "export_png_transparent": True,
        "export_pdf": True,
        "export_mp4": True,
    }
}



# ===========================================
# 🧠 IA QUOTAS — compteur par jour par user
# ===========================================

def can_use_ia_background(db: Session, user: User) -> bool:
    """Vérifie si l’utilisateur peut encore générer un background IA aujourd’hui"""

    limits = PLAN_LIMITS[user.plan]

    # Vérifier le compteur IA
    today = datetime.utcnow().date()

    status = (
        db.query(IAStatus)
        .filter(IAStatus.user_id == user.id)
        .filter(IAStatus.date == today)
        .first()
    )

    if not status:
        return True

    # Limite atteinte ?
    return status.background_count < limits["ia_background_per_day"]


def register_ia_background_use(db: Session, user: User):
    """Incrémente l’usage IA du jour"""

    today = datetime.utcnow().date()

    status = (
        db.query(IAStatus)
        .filter(IAStatus.user_id == user.id)
        .filter(IAStatus.date == today)
        .first()
    )

    if not status:
        status = IAStatus(
            user_id=user.id,
            date=today,
            background_count=1
        )
        db.add(status)
    else:
        status.background_count += 1

    db.commit()
