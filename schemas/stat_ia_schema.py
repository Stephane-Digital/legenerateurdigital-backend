from pydantic import BaseModel
from typing import Optional


# ============================================================
# 🔄 IA STATUS UPDATE SCHEMA
# ============================================================
class IAStatusUpdateSchema(BaseModel):
    status: Optional[str] = None   # "idle", "generating", "error"
    message: Optional[str] = None  # Optional descriptive message
