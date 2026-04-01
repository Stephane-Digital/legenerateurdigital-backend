from pydantic import BaseModel
from typing import Optional


class LeadMemoryCreate(BaseModel):
    memory_type: str = "brief"
    content: str
    emotional_profile: Optional[str] = None
    business_context: Optional[str] = None


class LeadGenerateRequest(BaseModel):
    goal: str
    brief: str
    emotional_style: Optional[str] = "human premium"
    business_context: Optional[str] = None
