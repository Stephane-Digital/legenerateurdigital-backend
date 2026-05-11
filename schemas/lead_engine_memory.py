from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LeadMemoryCreate(BaseModel):
    memory_type: str = Field(default="brief", max_length=80)
    goal: Optional[str] = Field(default=None, max_length=120)
    content: str = Field(..., min_length=1)
    emotional_profile: Optional[str] = None
    business_context: Optional[str] = None
    metadata_json: Optional[str] = None


class LeadGenerateRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=120)
    brief: str = Field(..., min_length=1, max_length=12000)
    emotional_style: Optional[str] = Field(default="humain, authentique, expert")
    business_context: Optional[str] = None

    # LGD V8 — branchement réel du Copilote IA.
    # Ces champs sont optionnels pour ne pas casser les anciens appels frontend.
    objective: Optional[str] = Field(default=None, max_length=120)
    angle: Optional[str] = Field(default=None, max_length=120)
    audience: Optional[str] = Field(default=None, max_length=160)
    tone: Optional[str] = Field(default=None, max_length=120)
    max_length: Optional[int] = Field(default=None, ge=40, le=1200)
    cta_url: Optional[str] = Field(default=None, max_length=600)
    page_type: Optional[str] = Field(default=None, max_length=120)


class LeadMemoryOut(BaseModel):
    id: int
    user_id: int
    memory_type: str
    goal: Optional[str] = None
    content: str
    emotional_profile: Optional[str] = None
    business_context: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: Optional[str] = None


class LeadGenerateResponse(BaseModel):
    content: str
    memory_items_used: int = 0
