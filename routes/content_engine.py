from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from models.user_model import User
from services.content_engine_service import generate_content

from schemas.content_engine_schema import ContentRequestSchema

router = APIRouter(prefix="/content-engine", tags=["Content Engine"])


# ============================================================
# 🧠 GENERATE CONTENT (IA TEXT ENGINE)
# ============================================================
@router.post("/generate")
def generate(
    payload: ContentRequestSchema,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = generate_content(
        user_id=user.id,
        topic=payload.topic,
        tone=payload.tone,
        length=payload.length,
        platform=payload.platform,
    )

    if not result:
        raise HTTPException(500, "Erreur IA ou contenu vide.")

    return {"result": result}
