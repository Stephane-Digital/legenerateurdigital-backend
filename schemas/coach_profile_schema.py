from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CoachProfileOut(BaseModel):
    user_id: int
    profile: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[str] = None
    level: Optional[str] = None
    time_per_day: Optional[int] = None

    class Config:
        from_attributes = True


class CoachProfileUpdateIn(BaseModel):
    """Partial update.

    - profile: merges shallowly into existing profile
    - intent/level/time_per_day: optional convenience fields
    """

    profile: Optional[Dict[str, Any]] = None
    intent: Optional[str] = None
    level: Optional[str] = None
    time_per_day: Optional[int] = None


class CoachProfileReplaceIn(BaseModel):
    """Full replace of the profile blob."""

    profile: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[str] = None
    level: Optional[str] = None
    time_per_day: Optional[int] = None
