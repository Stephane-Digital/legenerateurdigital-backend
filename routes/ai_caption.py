from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import update_quota
from services.ai_quota_service import get_or_create_quota

router = APIRouter(prefix="/ai-caption", tags=["AI Caption"])


class CaptionRequest(BaseModel):
    prompt: str
    network: str = "instagram"
    tone: str = "premium"
    objective: str = "conversion"
    existing_caption: str | None = None
    include_hashtags: bool = False
    include_cta: bool = False
    language: str = "fr"
    post_type: str = "post"
    media_type: str = "image"


def generate_caption_text(data: CaptionRequest):
    base = f"🚀 {data.prompt}\n\n"

    if data.network == "linkedin":
        body = "Voici une légende optimisée pour renforcer ton expertise."
    elif data.network == "facebook":
        body = "Voici une légende engageante pensée pour maximiser les interactions."
    else:
        body = "Voici une légende optimisée pour booster la visibilité de ton post."

    objective_map = {
        "conversion": "Passe à l’action dès maintenant.",
        "engagement": "Dis-moi en commentaire ce que tu en penses.",
        "lead": "Découvre comment attirer plus de prospects.",
        "visibility": "Augmente ta portée avec une communication premium.",
    }

    footer = objective_map.get(data.objective, "")

    hashtags = ""
    if data.include_hashtags:
        hashtags = "\n\n#marketingdigital #business #ia #lgd"

    cta = ""
    if data.include_cta:
        cta = "\n\n👉 Passe à l’action avec LGD."

    return f"{base}{body}\n\n{footer}{cta}{hashtags}"


@router.post("/generate")
def generate_caption(
    payload: CaptionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = int(user["id"] if isinstance(user, dict) else user.id)

    quota = get_or_create_quota(db, user_id, feature="coach")

    remaining = max(
        int(getattr(quota, "credits", 0))
        - int(getattr(quota, "tokens_used", 0)),
        0,
    )

    if remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {
                    "message": "Quota IA épuisé. Passe au plan supérieur."
                },
            },
        )

    updated = update_quota(db, user_id, 1, feature="coach")

    if updated is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {
                    "message": "Quota IA épuisé. Passe au plan supérieur."
                },
            },
        )

    new_remaining = max(
        int(getattr(updated, "credits", 0))
        - int(getattr(updated, "tokens_used", 0)),
        0,
    )

    caption = generate_caption_text(payload)

    return {
        "caption": caption,
        "quota": {
            "remaining": new_remaining
        },
        "upsell": {
            "show": new_remaining <= 5,
            "message": (
                "⚡ Plus que quelques crédits IA disponibles."
                if new_remaining <= 5
                else ""
            ),
        },
    }
