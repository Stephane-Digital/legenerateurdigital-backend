from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LibraryItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    file_url: str


class LibraryItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    file_url: Optional[str] = None


class LibraryItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    file_url: str
    created_at: datetime

    model_config = {"from_attributes": True}
