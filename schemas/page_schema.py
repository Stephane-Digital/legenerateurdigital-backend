from pydantic import BaseModel
from typing import Optional

class SalesPageCreate(BaseModel):
    title: str
    audience: Optional[str] = None
    benefits: Optional[str] = None
    tone: Optional[str] = None

class SalesPageUpdate(BaseModel):
    title: str
    audience: Optional[str]
    benefits: Optional[str]
    tone: Optional[str]

class SalesPageResponse(BaseModel):
    id: int
    title: str
    audience: Optional[str]
    benefits: Optional[str]
    tone: Optional[str]
    generated_content: Optional[str]

    class Config:
        from_attributes = True
