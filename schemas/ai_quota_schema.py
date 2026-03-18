# schemas/ai_quota_schema.py
from pydantic import BaseModel

class IAQuotaBase(BaseModel):
    text_quota: float
    image_quota: float
    carrousel_quota: float

class IAQuotaUpdateSchema(BaseModel):
    text_quota: float | None = None
    image_quota: float | None = None
    carrousel_quota: float | None = None

class IAQuotaOut(BaseModel):
    id: int
    user_id: int
    text_quota: float
    image_quota: float
    carrousel_quota: float

    class Config:
        from_attributes = True
