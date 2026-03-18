from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from config.settings import settings

router = APIRouter(prefix="/ia", tags=["IA Status"])


class IAStatusResponse(BaseModel):
    status: str
    openai_key_present: bool
    timestamp: datetime


@router.get("/status", response_model=IAStatusResponse)
def ia_status():
    return IAStatusResponse(
        status="ok",
        openai_key_present=bool(settings.OPENAI_API_KEY),
        timestamp=datetime.utcnow()
    )
