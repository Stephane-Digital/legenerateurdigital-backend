from pydantic import BaseModel
from typing import Optional, Any


class SlideLibraryCreate(BaseModel):
    name: str
    category: Optional[str] = None
    data: Any     # slide complet


class SlideLibraryResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    data: Any

    class Config:
        orm_mode = True
