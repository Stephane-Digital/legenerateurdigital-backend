from pydantic import BaseModel
from typing import List, Any

class PlannerScheduleIn(BaseModel):
    carrousel_id: int
    slides: List[Any]
    network: str
    date: str
    time: str
