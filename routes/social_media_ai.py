from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.ai_image_service import generate_image
from routes.auth import get_current_user

from models.user_model import User

router = APIRouter(prefix="/ia/image", tags=["Social IA"])


class ImagePrompt(BaseModel):
    prompt: str
    ratio: str = "square"  # square, portrait, landscape


@router.post("/generate")
def generate_social_image(
    data: ImagePrompt,
    user: User = Depends(get_current_user)
):
    try:
        img_b64 = generate_image(data.prompt, data.ratio)
        return {"image_base64": img_b64}
    except Exception as e:
        raise HTTPException(500, f"Generation error: {e}")
