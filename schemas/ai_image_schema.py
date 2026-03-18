from pydantic import BaseModel
from typing import Optional


# ============================================================
# 🎨 IMAGE GENERATION — Nouveau schéma requis pour ai_image_routes
# ============================================================
class AIImageRequestSchema(BaseModel):
    prompt: str                      # description de l'image
    style: Optional[str] = None      # style artistique (réaliste, cartoon…)
    size: Optional[str] = "1024x1024"  # taille par défaut


# ============================================================
# 🎨 BACKGROUND IA (ancien module existant)
# ============================================================
class AIGenerateRequest(BaseModel):
    prompt: str
    style: str = "premium"


class AIGenerateResponse(BaseModel):
    url: str
    style: str
    remaining_quota: float | int


# ============================================================
# 🎨 DÉGRADÉ IA (ancien module existant)
# ============================================================
class AIGradientRequest(BaseModel):
    palette: str = "gold"


class AIGradientResponse(BaseModel):
    colors: list[str]
    type: str
    remaining_quota: float | int


# ============================================================
# 🎨 PRESET DESIGN (ancien module existant)
# ============================================================
class AIPresetRequest(BaseModel):
    preset: str = "halo-gold"


class AIPresetResponse(BaseModel):
    background: str
    effect: str | None
    remaining_quota: float | int
