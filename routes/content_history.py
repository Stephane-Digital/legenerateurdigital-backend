from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel

from database import get_db
from services.auth_service import get_current_user
from models.content_history_model import ContentHistory

router = APIRouter(prefix="/content-history", tags=["Content History"])


class ContentHistoryOut(BaseModel):
    id: int
    user_id: int
    content_type: str
    payload: dict
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ContentHistoryOut])
def list_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    history = (
        db.query(ContentHistory)
        .filter(ContentHistory.user_id == user.id)
        .order_by(ContentHistory.created_at.desc())
        .limit(200)
        .all()
    )
    return history
