from pydantic import BaseModel

class SocialPostGenerate(BaseModel):
    reseau: str
    topic: str
