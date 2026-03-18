from pydantic import BaseModel
from typing import Optional

# -------------------------
# Création d’un plan
# -------------------------
class PlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    is_active: bool = True
    features: Optional[str] = None


# -------------------------
# Mise à jour d’un plan
# -------------------------
class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None
    features: Optional[str] = None


# -------------------------
# Réponse API
# -------------------------
class PlanResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    is_active: bool
    features: Optional[str]

    class Config:
        from_attributes = True
