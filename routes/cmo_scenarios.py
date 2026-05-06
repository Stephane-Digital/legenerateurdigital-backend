from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/cmo-scenarios", tags=["CMO Scenarios"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ScenarioPayload(BaseModel):
    offer: str
    target: str
    objective: str
    blocker: str
    offerType: str
    prospectLevel: str


SYSTEM_PROMPT = """
Tu es le moteur stratégique du CMO IA LGD.

Tu génères des scénarios marketing concrets.
Tu ne génères PAS des conseils vagues.

Retour STRICT en JSON.
"""


@router.post("/generate")
async def generate_scenarios(payload: ScenarioPayload) -> Dict[str, Any]:
    try:
        user_prompt = f"""
OFFRE:
{payload.offer}

CIBLE:
{payload.target}

OBJECTIF:
{payload.objective}

BLOCAGE:
{payload.blocker}

TYPE OFFRE:
{payload.offerType}

NIVEAU:
{payload.prospectLevel}

Génère 5 scénarios marketing.
"""

        response = client.chat.completions.create(
            model="gpt-5",
            temperature=0.9,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        return {
            "success": True,
            "content": content,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
