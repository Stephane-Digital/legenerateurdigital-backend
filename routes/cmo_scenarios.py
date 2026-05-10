from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/cmo-scenarios", tags=["CMO Scenarios"])


class ScenarioPayload(BaseModel):
    offer: str = ""
    target: str = ""
    objective: str = ""
    blocker: str = ""
    offerType: str = ""
    prospectLevel: str = ""


@router.post("/generate")
async def generate_scenarios(payload: ScenarioPayload) -> Dict[str, Any]:
    """
    LGD — CMO Scenarios removed.

    This endpoint is intentionally disabled to prevent any accidental OpenAI
    consumption. The product now uses the direct CMO Dispatch flow:
    CMO -> module payload -> Emailing IA / Coach / Lead Engine / Editor.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Le module Scénarios CMO a été supprimé. "
            "Utilise désormais le CMO Dispatch direct vers les modules LGD."
        ),
    )
