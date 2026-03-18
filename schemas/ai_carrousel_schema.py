from pydantic import BaseModel

class CarrouselPresetRequest(BaseModel):
    prompt: str
    slides_count: int
