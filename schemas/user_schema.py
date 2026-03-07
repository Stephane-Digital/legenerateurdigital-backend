# ============================================================
# 🧩 USER SCHEMAS — LGD 2025
# ============================================================

from pydantic import BaseModel, EmailStr
from typing import Optional


# ============================================================
# 🔹 Création utilisateur (Register)
# ============================================================

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


# ============================================================
# 🔹 Mise à jour utilisateur
# ============================================================

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None


# ============================================================
# 🔹 Réponse utilisateur (API)
# ============================================================

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr

    class Config:
        from_attributes = True
