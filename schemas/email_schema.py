from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailGenerateRequest(BaseModel):
    subject: str
    prompt: str
    model: Optional[str] = "gpt-4o-mini"


class EmailResponse(BaseModel):
    id: int
    subject: str
    content: str
    model_used: str
    tokens_used: int
    created_at: datetime

    class Config:
        from_attributes = True
