from pydantic import BaseModel
from typing import Optional, List, Tuple


# ============ BACKGROUND =============
class AIBackgroundRequest(BaseModel):
    prompt: str
    style: str = "premium"


class AIBackgroundResponse(BaseModel):
    url: str
    style: str
    remaining_quota: float


# ============ GRADIENT =============
class AIGradientRequest(BaseModel):
    palette: str = "gold"


class AIGradientResponse(BaseModel):
    type: str
    colors: List[str]
    remaining_quota: float


# ============ PRESET =============
class AIPresetRequest(BaseModel):
    preset: str


class AIPresetResponse(BaseModel):
    background: str
    effect: Optional[str]
    remaining_quota: float


# ============ UPLOAD =============
class AIUploadResponse(BaseModel):
    image_url: str
    format: str
    remaining_quota: float


# ============ COMPOSE =============
class AIComposeRequest(BaseModel):
    background_url: Optional[str]
    image_url: Optional[str]
    text: Optional[str]
    format: str
    position: Tuple[int, int] = (50, 50)
    filter: Optional[str] = None


class AIComposeResponse(BaseModel):
    composed_url: str
    remaining_quota: float


# ============ EXPORT =============
class AIExportRequest(BaseModel):
    compose_url: str


class AIExportResponse(BaseModel):
    export_url: str
    remaining_quota: float
