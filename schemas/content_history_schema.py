from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ContentHistoryCreate(BaseModel):
    action: str
    payload: Optional[str] = None


class ContentHistoryOut(BaseModel):
    id: int
    action: str
    payload: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
