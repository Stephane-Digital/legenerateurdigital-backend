from pydantic import BaseModel

class AIGenerateRequest(BaseModel):
    prompt: str
    type: str | None = "default"

class AIGenerateResponse(BaseModel):
    content: str
    model: str = "gpt-4o-mini"
