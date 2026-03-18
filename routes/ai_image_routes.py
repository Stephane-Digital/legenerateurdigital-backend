from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from models.user_model import User
from services.ai_image_service import generate_image
from schemas.ai_image_schema import AIImageRequestSchema

router = APIRouter(prefix="/ai-image", tags=["AI Image"])


# ============================================================
# 🎨 GENERATE IMAGE (IA)
# ============================================================
@router.post("/generate")
def generate_ai_image(
    payload: AIImageRequestSchema,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = generate_image(
        user_id=user.id,
        prompt=payload.prompt,
        style=payload.style,
        size=payload.size,
    )

    if not result:
        raise HTTPException(500, "Erreur IA, impossible de générer l'image.")

    return {"image_url": result}
