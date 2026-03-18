from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SocialPostCreateSchema(BaseModel):
    reseau: str
    contenu: Any
    date_programmee: Optional[datetime] = None
    statut: Optional[str] = "scheduled"
    supprimer_apres: bool = False

    # ✅ Tolérance: certains fronts envoient encore ces champs
    titre: Optional[str] = None
    format: Optional[str] = None
    archive: Optional[bool] = None


class SocialPostResponseSchema(BaseModel):
    id: int
    user_id: int

    # ✅ Champs réseau (compat)
    reseau: str
    network: Optional[str] = None

    statut: str

    # ✅ Meta (compat planner/front)
    titre: Optional[str] = None
    title: Optional[str] = None
    format: Optional[str] = None

    # ✅ Contenu: on renvoie un objet si possible (sinon string brut)
    contenu: Any

    # ✅ Date (compat)
    date_programmee: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None

    supprimer_apres: bool

    model_config = {"from_attributes": True}


# ✅ Compat: certaines routes importent encore ce nom depuis ce fichier
class SocialPostLogResponse(BaseModel):
    id: int
    user_id: int
    post_id: Optional[int] = None

    network: str
    content: Optional[str] = None

    status: str
    message: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}
