from pydantic import BaseModel
from typing import Optional


# ============================================================
# 🔄 IA STATUS UPDATE SCHEMA  (stabilité & Worker IA)
# ============================================================
class IAStatusUpdateSchema(BaseModel):
    status: Optional[str] = None      # ex : "idle", "generating", "error"
    message: Optional[str] = None     # message optionnel
