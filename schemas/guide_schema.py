from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GuideCreate(BaseModel):
    title: str
    description: Optional[str] = None
    content: Optional[str] = None


class GuideUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class GuideOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    content: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
