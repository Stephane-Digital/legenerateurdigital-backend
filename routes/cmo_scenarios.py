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
        raise ValueError("Réponse IA vide.")

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
Tu es le CMO IA premium de LGD, spécialisé marketing digital, MRR, infoproduits,
business en ligne, Systeme.io et prospects bloqués par l'inaction.

MISSION :
Génère exactement 1 scénario marketing premium, dense mais compact, en JSON valide.
Le scénario doit nourrir directement Emailing IA avec un contexte psychologique exploitable.

RÉPONSE STRICTE :
- JSON uniquement.
- Aucun markdown.
- Aucun texte hors JSON.
- Aucun champ vide.
- Phrases courtes, concrètes, humaines.
- Ne pas écrire un roman.

FORMAT EXACT :
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
      "recommended": true,
      "psychologicalTension": "...",
      "strategicMistake": "...",
      "costOfInaction": "...",
      "conversionMechanism": "...",
      "executionPlan": "...",
      "emailSequenceDirection": "...",
      "whyNow": "...",
      "emotional_pains": ["...", "...", "..."],
      "hidden_frustrations": ["...", "...", "..."],
      "daily_situations": ["...", "...", "..."],
      "inner_dialogue": ["...", "...", "..."],
      "false_beliefs": ["...", "...", "..."],
      "conversion_triggers": ["...", "...", "..."]
    }
  ]
}

RÈGLES QUALITÉ :
- Le scénario doit être spécifique à l'offre, la cible, l'objectif et le blocage fournis.
- Pour MRR / business en ligne, montre la différence entre apprendre, préparer et exposer vraiment une offre au marché.
- Utilise des scènes concrètes : brouillon, page visible, lien envoyé, premier clic, prospect réel, preuve marché.
- Évite les phrases génériques comme “passer à l'action” sauf si elles sont reliées à une action visible.
- Chaque champ doit ajouter une information nouvelle.
- Pas de promesse irréaliste.
- Ton : lucide, humain, stratégique, orienté conversion.

TAILLE :
- title : 8 à 14 mots.
- objective, angle, realProblem, context, whyItConverts : 1 à 2 phrases.
- champs premium : 1 phrase.
- listes : 3 éléments courts.
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

MISSION PREMIUM :
Génère 1 scénario marketing premium compact, directement exploitable par le CMO et Emailing IA.
Le scénario doit relier le blocage à une action commerciale visible : page publiée, lien envoyé, premier clic ou test marché.
Réponds uniquement avec le JSON demandé.
""".strip()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1100,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Réponse IA vide.")

        parsed = _extract_json_payload(content)

        scenarios = parsed.get("scenarios")
        if not isinstance(scenarios, list) or len(scenarios) == 0:
            raise ValueError("Réponse IA invalide : clé scenarios absente ou vide.")

        quota = update_quota(db, user_id, 1_200, feature="global")
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
