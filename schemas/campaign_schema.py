from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CampaignCreate(BaseModel):
    title: str
    description: Optional[str] = None
    json_data: Optional[str] = None


class CampaignOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    json_data: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
