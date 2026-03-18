from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AutomationCreate(BaseModel):
    name: str
    type: str


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


class AutomationOut(BaseModel):
    id: int
    name: str
    type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
