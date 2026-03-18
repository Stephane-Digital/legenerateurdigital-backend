from pydantic import BaseModel
from typing import Optional


# ============================================================
# 🎯 SCHEMA FOR CONTENT REQUEST (IA GENERATION)
# ============================================================
class ContentRequestSchema(BaseModel):
    topic: str                 # ex: "Marketing digital"
    tone: Optional[str] = None # ex: "professionnel", "amical"
    length: Optional[int] = 150  # nombre de mots
    platform: Optional[str] = None  # ex: "instagram", "tiktok"
