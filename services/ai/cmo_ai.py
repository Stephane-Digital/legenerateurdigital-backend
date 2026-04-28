from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = """
Tu es CMO IA V5, le cerveau marketing autonome de Le Générateur Digital.

Rôle :
- Chief Marketing Officer IA,
- stratège business,
- copywriter conversion,
- coach d'exécution,
- assistant anti-dispersion.

Ta mission :
Tu ne donnes pas une liste d'idées génériques.
Tu prends une décision marketing claire, tu expliques pourquoi, puis tu fournis une action prioritaire directement exploitable.

Méthode invisible :
1. comprendre l'objectif réel,
2. identifier le blocage principal,
3. choisir le levier le plus rentable maintenant,
4. décider la prochaine meilleure action,
5. générer le contenu ou le plan associé.

Règles :
- réponse en français ;
- concret, direct, utile ;
- pas de blabla ;
- pas de promesses irréalistes ;
- pas de jargon inutile ;
- si le brief est incomplet, fais des hypothèses raisonnables et indique-les ;
- une priorité claire vaut mieux que dix idées floues ;
- toujours produire une sortie exploitable immédiatement.
""".strip()


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("Le package openai n'est pas installé sur le backend.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _choose_model() -> str:
    return (
        os.getenv("OPENAI_CMO_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {
        "diagnostic": raw.strip(),
        "priority_action": "Clarifier l'action prioritaire.",
        "why_this_action": "La réponse n'a pas pu être structurée en JSON, mais le contenu brut est conservé.",
        "execution_plan": [],
        "generated_content": {
            "post": "",
            "email": "",
            "cta": "",
            "lead_magnet_idea": "",
        },
        "next_best_action": "Relancer une demande plus précise.",
        "risk_to_avoid": "Ne pas multiplier les actions sans priorité.",
    }


def _build_prompt(
    *,
    objective: str,
    niche: str,
    audience: str,
    offer: str,
    current_situation: str,
    constraints: str,
    preferred_channel: str,
    tone: str,
    user_level: str,
) -> str:
    return f"""
OBJECTIF UTILISATEUR
{objective or "non précisé"}

CONTEXTE BUSINESS
- Niche : {niche or "non précisée"}
- Audience : {audience or "non précisée"}
- Offre : {offer or "non précisée"}
- Situation actuelle : {current_situation or "non précisée"}
- Contraintes : {constraints or "non précisées"}
- Canal préféré : {preferred_channel or "à recommander"}
- Ton : {tone or "premium, humain, direct"}
- Niveau utilisateur : {user_level or "intermediate"}

TA MISSION CMO
1. Diagnostiquer le vrai problème marketing.
2. Choisir UNE action prioritaire maintenant.
3. Expliquer brièvement pourquoi c'est l'action la plus rentable.
4. Donner un plan d'exécution simple.
5. Générer un contenu exploitable associé.
6. Donner la prochaine meilleure action.

FORMAT STRICT — JSON VALIDE UNIQUEMENT
{{
  "diagnostic": "diagnostic clair en 3 à 6 lignes",
  "priority_action": "une action prioritaire claire",
  "why_this_action": "pourquoi cette action est la plus rentable maintenant",
  "execution_plan": [
    {{"step": 1, "title": "...", "detail": "..."}},
    {{"step": 2, "title": "...", "detail": "..."}}
  ],
  "generated_content": {{
    "post": "un post prêt à publier si pertinent",
    "email": "un email court prêt à adapter si pertinent",
    "cta": "un CTA clair",
    "lead_magnet_idea": "une idée de lead magnet si pertinent"
  }},
  "next_best_action": "la prochaine action à faire juste après",
  "risk_to_avoid": "le piège principal à éviter"
}}
""".strip()


def generate_cmo_strategy(
    *,
    objective: str,
    niche: str = "",
    audience: str = "",
    offer: str = "",
    current_situation: str = "",
    constraints: str = "",
    preferred_channel: str = "",
    tone: str = "premium, humain, direct",
    user_level: str = "intermediate",
) -> Dict[str, Any]:
    if not _clean(objective):
        raise ValueError("objective est requis.")

    prompt = _build_prompt(
        objective=_clean(objective),
        niche=_clean(niche),
        audience=_clean(audience),
        offer=_clean(offer),
        current_situation=_clean(current_situation),
        constraints=_clean(constraints),
        preferred_channel=_clean(preferred_channel),
        tone=_clean(tone, "premium, humain, direct"),
        user_level=_clean(user_level, "intermediate"),
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=_choose_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.58,
        max_tokens=1800,
    )

    content = ""
    try:
        content = (response.choices[0].message.content or "").strip()
    except Exception:
        content = ""

    if not content:
        raise RuntimeError("Réponse OpenAI vide pour CMO IA V5.")

    data = _safe_json_loads(content)
    data["meta"] = {
        "module": "CMO IA V5",
        "mode": "next_best_action",
        "model": _choose_model(),
    }
    return data
