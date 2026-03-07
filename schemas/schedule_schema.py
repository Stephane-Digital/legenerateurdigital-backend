from pydantic import BaseModel
from datetime import datetime
from typing import Any, Optional


class SchedulePostRequest(BaseModel):
    reseau: str
    date_programmee: datetime
    format: Optional[str] = "post"
    contenu: Optional[dict] = None


class ScheduleCarrouselRequest(BaseModel):
    reseau: str
    date_programmee: datetime
    format: Optional[str] = "carrousel"
    carrousel_id: Optional[int] = None
    slides: Optional[list] = None


class ScheduleResponse(BaseModel):
    id: int
    statut: str
    reseau: str
    date_programmee: datetime

    # ✅ compat front (certains composants utilisent scheduled_at)
    scheduled_at: Optional[datetime] = None

    # ✅ enrichissements utiles UI/debug
    kind: Optional[str] = None
    format: Optional[str] = None
    titre: Optional[str] = None
    contenu: Optional[Any] = None


class PlannerPostOut(BaseModel):
    id: int
    reseau: str
    date_programmee: datetime
    scheduled_at: Optional[datetime] = None

    statut: Optional[str] = None
    kind: Optional[str] = None
    format: Optional[str] = None

    # ✅ affichage Planner / modale édition
    titre: str

    # ✅ dict pour preview/minia côté front
    contenu: Any
