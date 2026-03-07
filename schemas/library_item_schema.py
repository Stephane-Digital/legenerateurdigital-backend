from pydantic import BaseModel


class LibraryItemCreate(BaseModel):
    title: str
    type: str   # ex: "text", "image", "pdf", etc.
    content: str  # texte ou JSON selon l’usage

    class Config:
        from_attributes = True


class LibraryItemResponse(BaseModel):
    id: int
    title: str
    type: str
    content: str
    user_id: int

    class Config:
        from_attributes = True
