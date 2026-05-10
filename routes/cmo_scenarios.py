from __future__ import annotations

import json
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import get_or_create_quota, update_quota

router = APIRouter(prefix="/cmo-scenarios", tags=["CMO Scenarios"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ScenarioPayload(BaseModel):
    offer: str
    target: str
    objective: str
    blocker: str
    offerType: str
    prospectLevel: str


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def _quota_remaining(quota: Any) -> int:
    limit = _to_int(
        getattr(quota, "credits", None)
        or getattr(quota, "tokens_limit", None)
        or getattr(quota, "limit_tokens", None),
        0,
    )
    used = _to_int(
        getattr(quota, "tokens_used", None)
        or getattr(quota, "used_tokens", None),
        0,
    )
    remaining = _to_int(getattr(quota, "remaining", None), -1)
    if remaining >= 0:
        return remaining
    if limit > 0:
        return max(limit - used, 0)
    return 0


def _extract_json_payload(content: str) -> Dict[str, Any]:
    """
    LGD SAFE JSON PARSER
    Récupère un JSON valide même si le modèle ajoute accidentellement
    un court texte avant/après. Aucun quota n'est débité si le JSON reste invalide.
    """
    raw = str(content or "").strip()
    if not raw:
        return {"scenarios": []}

    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start : end + 1].strip()
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Réponse IA invalide : JSON impossible à analyser.")


SYSTEM_PROMPT = """
Tu es le CMO senior de LGD.

MISSION :
Créer EXACTEMENT 1 scénario marketing premium ultra-actionnable.

OBJECTIF :
Créer le meilleur pont entre le blocage réel du prospect
et une action commerciale visible.

RÈGLES :
- JSON valide uniquement
- aucun texte hors JSON
- concret, émotionnel, stratégique
- zéro remplissage
- phrases courtes
- pensé pour nourrir Emailing IA

FORMAT :
{
 "scenarios":[
   {
    "id":"awareness",
    "badge":"ACTION PRIORITAIRE RECOMMANDÉE",
    "title":"",
    "objective":"",
    "angle":"",
    "realProblem":"",
    "context":"",
    "whyItConverts":"",
    "recommended":true,
    "psychologicalTension":"",
    "strategicMistake":"",
    "costOfInaction":"",
    "conversionMechanism":"",
    "executionPlan":"",
    "emailSequenceDirection":"",
    "whyNow":""
   }
 ]
}

IMPORTANT :
Le scénario doit être premium mais compact.
Pas de roman.
Pas de généralités.
""".strip()


@router.post("/generate")
async def generate_scenarios(
    payload: ScenarioPayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        user_id = _user_id(current_user)

        quota_check = get_or_create_quota(db, user_id, feature="global")
        if _quota_remaining(quota_check) <= 0:
            raise HTTPException(status_code=402, detail="Quota IA journalier ou mensuel atteint")

        safe_offer = (payload.offer or "")[:250]
        safe_target = (payload.target or "")[:250]
        safe_objective = (payload.objective or "")[:300]
        safe_blocker = (payload.blocker or "")[:300]

        user_prompt = f"""
OFFRE :
{safe_offer}

CIBLE :
{safe_target}

OBJECTIF :
{safe_objective}

BLOCAGE :
{safe_blocker}

TYPE :
{payload.offerType}

NIVEAU :
{payload.prospectLevel}

MISSION :
Créer 1 scénario premium directement exploitable
par CMO + Emailing IA.
Le scénario doit pousser vers une action visible.
""".strip()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=850,
        )

        content = response.choices[0].message.content

        if not content:
            content = json.dumps({
                "scenarios": [{
                    "id": "awareness",
                    "badge": "ACTION PRIORITAIRE RECOMMANDÉE",
                    "title": "Débloquer une première action visible",
                    "objective": safe_objective,
                    "angle": "Transformer le faux travail en action marché.",
                    "realProblem": safe_blocker,
                    "context": safe_offer,
                    "whyItConverts": "Le prospect passe enfin à une action visible.",
                    "recommended": True,
                    "psychologicalTension": "Le prospect prépare au lieu d'exposer.",
                    "strategicMistake": "Perfectionner ce qui reste invisible.",
                    "costOfInaction": "Chaque jour retarde les premiers signaux marché.",
                    "conversionMechanism": "Publier, envoyer, tester.",
                    "executionPlan": "Créer → publier → tester",
                    "emailSequenceDirection": "Faire passer du brouillon à l'action.",
                    "whyNow": "Le marché répond uniquement à ce qui est visible."
                }]
            })

        parsed = _extract_json_payload(content)

        scenarios = parsed.get("scenarios")
        if not isinstance(scenarios, list) or len(scenarios) == 0:
            raise ValueError("Réponse IA invalide : clé scenarios absente ou vide.")

        quota = update_quota(db, user_id, 900, feature="global")
        if quota is None:
            raise HTTPException(status_code=402, detail="Quota IA journalier ou mensuel atteint")

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

        premium_keys = {
            "psychologicalTension",
            "strategicMistake",
            "costOfInaction",
            "conversionMechanism",
            "executionPlan",
            "emailSequenceDirection",
            "whyNow",
            "emotional_pains",
            "hidden_frustrations",
            "daily_situations",
            "inner_dialogue",
            "false_beliefs",
            "conversion_triggers",
        }

        normalized_scenarios = []

        for index, scenario in enumerate(scenarios[:1], start=1):
            if not isinstance(scenario, dict):
                raise ValueError(f"Réponse IA invalide : scénario {index} n'est pas un objet.")

            scenario.setdefault("id", f"scenario_{index}")
            scenario.setdefault("badge", "SCÉNARIO IA PREMIUM")
            scenario.setdefault("title", "Scénario marketing premium")
            scenario.setdefault("objective", payload.objective)
            scenario.setdefault("angle", "Angle marketing premium adapté au blocage réel du prospect.")
            scenario.setdefault("realProblem", payload.blocker)
            scenario.setdefault("context", payload.offer)
            scenario.setdefault(
                "whyItConverts",
                "Ce scénario convertit parce qu'il relie le blocage réel du prospect à une action commerciale concrète et visible."
            )
            scenario.setdefault("recommended", index == 1)

            scenario.setdefault(
                "psychologicalTension",
                "Le prospect veut obtenir un résultat, mais continue à se protéger derrière la préparation au lieu d'exposer son offre au marché."
            )
            scenario.setdefault(
                "strategicMistake",
                "La mauvaise priorité consiste à perfectionner ce qui reste invisible au lieu de tester une première version auprès de vrais prospects."
            )
            scenario.setdefault(
                "costOfInaction",
                "Chaque jour sans page visible, message envoyé ou test réel retarde les premiers signaux du marché."
            )
            scenario.setdefault(
                "conversionMechanism",
                "Le scénario transforme une frustration abstraite en action mesurable : publier, envoyer, tester, puis améliorer avec des retours réels."
            )
            scenario.setdefault(
                "executionPlan",
                "1. Clarifier l'offre en une phrase. 2. Publier une première page visible. 3. Envoyer le lien à une audience ou à des prospects réels."
            )
            scenario.setdefault(
                "emailSequenceDirection",
                "La séquence doit partir du faux travail quotidien, révéler le coût de l'offre invisible, puis amener vers une première action simple et mesurable."
            )
            scenario.setdefault(
                "whyNow",
                "Le meilleur moment n'est pas quand tout est parfait, mais quand le prospect peut enfin obtenir un premier signal réel du marché."
            )
            scenario.setdefault(
                "emotional_pains",
                [
                    "Il a investi dans des formations sans obtenir de vente concrète.",
                    "Il se sent en retard quand il voit les résultats des autres.",
                    "Il doute de sa capacité à transformer ce qu'il sait en revenu réel.",
                ],
            )
            scenario.setdefault(
                "hidden_frustrations",
                [
                    "Il prépare beaucoup mais publie peu.",
                    "Il a peur que son offre soit jugée trop simple ou pas assez professionnelle.",
                    "Il confond progression et accumulation de nouvelles méthodes.",
                ],
            )
            scenario.setdefault(
                "daily_situations",
                [
                    "Canva reste ouvert pendant des heures sans publication.",
                    "Le tunnel Systeme.io est presque prêt mais le lien n'est pas envoyé.",
                    "Les notes s'accumulent dans Notion pendant que l'offre reste invisible.",
                ],
            )
            scenario.setdefault(
                "inner_dialogue",
                [
                    "Il me manque encore une bonne stratégie.",
                    "Je publierai quand ce sera plus propre.",
                    "Si personne ne clique, ça voudra dire que je ne suis pas fait pour ça.",
                ],
            )
            scenario.setdefault(
                "false_beliefs",
                [
                    "Il faut être parfaitement prêt avant de vendre.",
                    "Une formation de plus supprimera le blocage.",
                    "Un tunnel imparfait ne peut pas générer de premier signal utile.",
                ],
            )
            scenario.setdefault(
                "conversion_triggers",
                [
                    "Une première page visible vaut mieux qu'un tunnel parfait caché.",
                    "Un premier clic donne plus d'informations qu'une nouvelle vidéo.",
                    "Le marché ne peut répondre qu'à ce qui lui est montré.",
                ],
            )

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

            for key in premium_keys:
                value = scenario.get(key)
                if isinstance(value, list):
                    if not value:
                        scenario[key] = ["À préciser par le CMO IA selon le contexte du scénario."]
                elif not str(value or "").strip():
                    scenario[key] = "À préciser par le CMO IA selon le contexte du scénario."

            normalized_scenarios.append(scenario)

        return {
            "success": True,
            "scenarios": normalized_scenarios,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
