from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user_model import User
from routes.auth import get_current_user
from services.ai.carrousel_ai import (
    generate_preset_ai,
    generate_background_ai,
    generate_from_slides_ai,
)

router = APIRouter(prefix="/ai/carrousel", tags=["AI Carrousel"])


@router.post("/preset")
def ai_generate_preset(payload: dict, db: Session = Depends(get_db)):
    return generate_preset_ai(payload)


@router.post("/background")
def ai_generate_background(payload: dict, db: Session = Depends(get_db)):
    return generate_background_ai(payload)


@router.post("/create-from-slides")
def ai_create_from_slides(payload: dict, db: Session = Depends(get_db)):
    return generate_from_slides_ai(payload)
