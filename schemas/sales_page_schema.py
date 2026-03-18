from pydantic import BaseModel
from typing import Optional, Any


# ============================================================
# 📝 CREATE SCHEMA
# ============================================================

class SalesPageCreateSchema(BaseModel):
    title: str
    description: Optional[str] = None
    generated_content: Optional[Any] = None  # JSON text


# ============================================================
# 📝 UPDATE SCHEMA
# ============================================================

class SalesPageUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    generated_content: Optional[Any] = None  # JSON text
