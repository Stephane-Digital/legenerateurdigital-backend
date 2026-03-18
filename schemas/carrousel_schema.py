from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ================================
# CARROUSEL CREATE / UPDATE
# ================================
class CarrouselCreate(BaseModel):
    title: str
    description: Optional[str] = None
    metadata: Optional[str] = None


class CarrouselUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[str] = None


# ================================
# SLIDES
# ================================
class CarrouselSlideCreate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    image_url: Optional[str] = None
    canvas_json: Optional[str] = None
    position: int


class CarrouselSlideUpdate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    image_url: Optional[str] = None
    canvas_json: Optional[str] = None
    position: Optional[int] = None


class CarrouselSlideOut(BaseModel):
    id: int
    title: Optional[str]
    text: Optional[str]
    image_url: Optional[str]
    canvas_json: Optional[str]
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================
# CARROUSEL OUT
# ================================
class CarrouselOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    metadata: Optional[str]
    created_at: datetime
    slides: List[CarrouselSlideOut] = []

    model_config = {"from_attributes": True}
