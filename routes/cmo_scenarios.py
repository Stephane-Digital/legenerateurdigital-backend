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
Tu es le moteur stratégique premium du CMO IA LGD.

Tu agis comme un CMO senior spécialisé en marketing digital, offres MRR, infoproduits,
business en ligne, tunnels Systeme.io, audiences bloquées par l'inaction et conversion.

Ta mission : générer 5 scénarios marketing PROFONDS, concrets et directement exploitables
par Le Générateur Digital.

Tu ne génères PAS :
- des conseils vagues ;
- des phrases motivationnelles ;
- du contenu générique ;
- des scénarios courts ;
- des recommandations superficielles ;
- des blocs qui pourraient être vrais pour n'importe quelle offre.

Tu dois répondre UNIQUEMENT en JSON valide.
Ne réponds jamais en markdown.
Ne mets jamais ```json.
N'ajoute aucun texte hors JSON.

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
      "recommended": true,
      "psychologicalTension": "...",
      "strategicMistake": "...",
      "costOfInaction": "...",
      "conversionMechanism": "...",
      "executionPlan": "...",
      "emailSequenceDirection": "...",
      "whyNow": "..."
    }
  ]
}

CLÉS OBLIGATOIRES MINIMALES POUR COMPATIBILITÉ FRONTEND :
- id
- badge
- title
- objective
- angle
- realProblem
- context
- whyItConverts
- recommended

CLÉS PREMIUM À AJOUTER À CHAQUE SCÉNARIO :
- psychologicalTension : tension psychologique réelle chez le prospect.
- strategicMistake : erreur stratégique qui maintient le prospect bloqué.
- costOfInaction : coût concret de continuer comme avant.
- conversionMechanism : mécanisme marketing qui rend le scénario persuasif.
- executionPlan : mini-plan d'action précis en 3 étapes courtes.
- emailSequenceDirection : direction exploitable par Emailing IA pour transformer ce scénario en séquence.
- whyNow : raison crédible d'agir maintenant, sans urgence artificielle.

RÈGLES STRICTES :
- Génère exactement 5 scénarios.
- Chaque scénario doit contenir toutes les clés obligatoires minimales.
- Chaque scénario doit aussi contenir les clés premium.
- Aucun champ ne doit être vide.
- Chaque scénario doit être spécifique à l'offre, à la cible, à l'objectif et au blocage fournis.
- Chaque champ doit être rédigé en français naturel.
- Chaque champ important doit faire 2 à 5 phrases quand c'est utile.
- Le rendu doit être premium, stratégique, dense, mais lisible.
- Le scénario doit pouvoir alimenter ensuite un CMO, une séquence email, une page de vente ou un lead magnet.
- Ne répète pas la même idée dans les 5 scénarios.
- Ne commence pas tous les scénarios avec la même structure.
- Ne répète pas mécaniquement le blocage fourni : interprète-le intelligemment.
- Ne promets pas de résultat irréaliste.
- Garde un ton humain, lucide, marketing, pas professoral.

LES 5 SCÉNARIOS DOIVENT COUVRIR :
1. Prise de conscience directe
   Montrer au prospect ce qu'il fait déjà qui l'empêche d'obtenir le résultat.

2. Erreur invisible
   Révéler le faux travail, la mauvaise priorité ou la croyance qui entretient le blocage.

3. Objection réelle
   Traiter la peur ou l'excuse dominante sans la caricaturer.

4. Solution claire
   Présenter le chemin le plus simple vers une action visible et testable.

5. Projection réaliste
   Projeter le prospect dans une situation concrète après une première action réussie.

CRITÈRES DE QUALITÉ PREMIUM :
- On doit sentir que le scénario comprend le marché.
- On doit sentir que le prospect est observé dans sa réalité quotidienne.
- On doit comprendre pourquoi ce scénario convertit.
- On doit pouvoir transformer le scénario en séquence email sans réécrire la stratégie.
- Les mots doivent être précis : page visible, offre testée, lien envoyé, premier clic, prospect réel, message clair, brouillon, preuve marché.
- Pour les offres MRR / business en ligne, insiste sur la différence entre apprendre, préparer et exposer réellement une offre au marché.
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

MISSION PREMIUM :
Génère exactement 5 scénarios marketing au format JSON obligatoire.
Chaque scénario doit être précis, dense, concret, exploitable dans le CMO LGD et adapté au contexte fourni.

Pour chaque scénario :
- explique le vrai levier psychologique ;
- montre le coût business de l'inaction ;
- donne un mécanisme marketing clair ;
- prépare implicitement une future séquence Emailing IA ;
- évite les phrases génériques comme "passer à l'action", sauf si elles sont reliées à une action concrète visible.

Le scénario recommandé doit être celui qui crée le meilleur pont entre le blocage actuel et une action commerciale rapide.
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

        premium_keys = {
            "psychologicalTension",
            "strategicMistake",
            "costOfInaction",
            "conversionMechanism",
            "executionPlan",
            "emailSequenceDirection",
            "whyNow",
        }

        normalized_scenarios = []

        for index, scenario in enumerate(scenarios[:5], start=1):
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
                if not str(scenario.get(key) or "").strip():
                    scenario[key] = "À préciser par le CMO IA selon le contexte du scénario."

            normalized_scenarios.append(scenario)

        return {
            "success": True,
            "scenarios": normalized_scenarios,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
