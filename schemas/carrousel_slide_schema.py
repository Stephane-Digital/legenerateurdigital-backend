# ============================================================
# 📘 SCHEMAS SLIDES CARROUSEL — LGD PREMIUM 2025 (SAFE FINAL)
# ============================================================

from pydantic import BaseModel
from typing import Optional, List, Any


# ============================================================
# 🟦 BASE SLIDE
# (aligné sur le modèle SQLAlchemy : title + json_layers)
# ============================================================

class CarrouselSlideBase(BaseModel):
    title: Optional[str] = ""
    json_layers: List[Any] = []

    class Config:
        extra = "ignore"


# ============================================================
# 🟩 SLIDE — RÉPONSE ORM (lecture BDD)
# ============================================================

class CarrouselSlideResponse(BaseModel):
    id: int
    position: int
    title: str
    json_layers: List[Any]

    class Config:
        from_attributes = True


# ============================================================
# 🟦 SLIDE — MISE À JOUR (unit)
# ============================================================

class CarrouselSlideUpdateSchema(BaseModel):
    title: Optional[str] = ""
    json_layers: List[Any] = []

    class Config:
        extra = "ignore"


# ============================================================
# 🟧 BULK UPDATE
# ============================================================

class CarrouselSlidesBulkUpdateSchema(BaseModel):
    slides: List[CarrouselSlideUpdateSchema]

    class Config:
        extra = "ignore"
