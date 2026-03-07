from pydantic import BaseModel


class SocialPostAIGenerateRequest(BaseModel):
    reseau: str
    sujet: str
    objectif: str | None = None
    tonalite: str | None = None


class SocialPostAIResponse(BaseModel):
    texte: str
    reseau: str
