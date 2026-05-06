from __future__ import annotations

import json
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

Tu génères des scénarios marketing concrets, directs et exploitables.
Tu ne génères PAS des conseils vagues.
Tu ne génères PAS de texte marketing générique.
Tu ne fais AUCUN fallback.

Tu dois répondre UNIQUEMENT en JSON valide.

FORMAT OBLIGATOIRE :

{
  "scenarios": [
    {
      "id": "awareness",
      "badge": "ACTION PRIORITAIRE RECOMMANDÉE",
      "title": "...",
      "objective": "...",
      "angle": "...",
      "realProblem": "...",
      "context": "...",
      "whyItConverts": "...",
      "recommended": true
    }
  ]
}

RÈGLES STRICTES :
- Génère exactement 5 scénarios.
- Chaque scénario doit contenir toutes les clés obligatoires.
- Aucun champ ne doit être vide.
- Chaque scénario doit être spécifique à l’offre, à la cible, à l’objectif et au blocage fournis.
- Ne réponds jamais en markdown.
- Ne mets jamais ```json.
- N’ajoute aucun texte hors JSON.

Les 5 scénarios doivent couvrir :
1. Prise de conscience directe
2. Erreur invisible
3. Objection réelle
4. Solution claire
5. Projection réaliste
""".strip()


@router.post("/generate")
async def generate_scenarios(payload: ScenarioPayload) -> Dict[str, Any]:
    try:
        user_prompt = f"""
OFFRE :
{payload.offer}

CIBLE :
{payload.target}

OBJECTIF BUSINESS :
{payload.objective}

BLOCAGE PRINCIPAL :
{payload.blocker}

TYPE D'OFFRE :
{payload.offerType}

NIVEAU DU PROSPECT :
{payload.prospectLevel}

Génère exactement 5 scénarios marketing au format JSON obligatoire.
Chaque scénario doit être précis, concret, exploitable dans le CMO LGD et adapté au contexte fourni.
""".strip()

        response = client.chat.completions.create(
            model="gpt-5",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Réponse IA vide.")

        parsed = json.loads(content)

        scenarios = parsed.get("scenarios")
        if not isinstance(scenarios, list) or len(scenarios) == 0:
            raise ValueError("Réponse IA invalide : clé scenarios absente ou vide.")

        required_keys = {
            "id",
            "badge",
            "title",
            "objective",
            "angle",
            "realProblem",
            "context",
            "whyItConverts",
            "recommended",
        }

        normalized_scenarios = []

        for index, scenario in enumerate(scenarios[:5], start=1):
            if not isinstance(scenario, dict):
                raise ValueError(f"Réponse IA invalide : scénario {index} n'est pas un objet.")

            scenario.setdefault("id", f"scenario_{index}")
            scenario.setdefault("badge", "SCÉNARIO IA")
            scenario.setdefault("title", "Scénario marketing")
            scenario.setdefault("objective", payload.objective)
            scenario.setdefault("angle", "Angle marketing")
            scenario.setdefault("realProblem", payload.blocker)
            scenario.setdefault("context", payload.offer)
            scenario.setdefault(
                "whyItConverts",
                "Ce scénario répond directement au blocage principal du prospect."
            )
            scenario.setdefault("recommended", index == 1)

            missing = [key for key in required_keys if key not in scenario]
            if missing:
                raise ValueError(
                    f"Réponse IA invalide : scénario {index} incomplet, clés manquantes : {', '.join(missing)}."
                )

            empty = [
                key for key in required_keys
                if key != "recommended" and not str(scenario.get(key) or "").strip()
            ]
            if empty:
                raise ValueError(
                    f"Réponse IA invalide : scénario {index} contient des champs vides : {', '.join(empty)}."
                )

            normalized_scenarios.append(scenario)

        return {
            "success": True,
            "scenarios": normalized_scenarios,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
