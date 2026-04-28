from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = """
Tu es Trend Radar V4, l'IA de veille intelligente de Le Générateur Digital.

Mission :
- analyser les mécaniques d'un contenu inspirant,
- comprendre pourquoi il peut performer,
- extraire les angles marketing utiles,
- produire une version 100% originale adaptée à un business,
- ne jamais copier le contenu source.

Règles absolues :
- ne copie jamais une phrase entière du contenu source ;
- ne reproduis pas l'identité, le style reconnaissable ou la signature d'un créateur ;
- analyse les mécaniques, pas le texte à voler ;
- transforme l'idée avec un angle différent si nécessaire ;
- reste utile, concret, business, humain et conversion-first ;
- si l'entrée est trop pauvre, formule des hypothèses utiles et indique-les clairement.
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
        os.getenv("OPENAI_TREND_RADAR_MODEL", "").strip()
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
        "analysis": {
            "hook": "",
            "angle": "",
            "pain": "",
            "desire": "",
            "format": "",
            "why_it_can_work": "",
            "anti_copy_safety": "Réponse non JSON, contenu brut conservé.",
        },
        "generated": {
            "post": raw.strip(),
            "email": "",
            "carrousel": [],
            "cta": "",
        },
        "recommendation": "",
    }


def _build_prompt(
    *,
    source_text: str,
    source_url: Optional[str],
    niche: str,
    audience: str,
    offer: str,
    objective: str,
    output_type: str,
    tone: str,
) -> str:
    url_block = f"URL fournie : {source_url}" if source_url else "URL fournie : aucune"
    return f"""
CONTEXTE UTILISATEUR
- Niche : {niche or "non précisée"}
- Audience : {audience or "non précisée"}
- Offre : {offer or "non précisée"}
- Objectif : {objective or "engagement + conversion"}
- Type de sortie souhaité : {output_type or "post"}
- Ton souhaité : {tone or "premium, humain, direct"}

SOURCE À ANALYSER
{url_block}

Contenu / idée / transcription fournie :
{source_text}

TÂCHE 1 — ANALYSE
Analyse uniquement les mécaniques :
1. hook utilisé,
2. angle marketing,
3. douleur ciblée,
4. désir déclenché,
5. format du contenu,
6. pourquoi cela peut performer,
7. risque de copie à éviter.

TÂCHE 2 — TRANSFORMATION LGD
Crée un contenu 100% original, adapté au contexte utilisateur.
Tu peux produire :
- un post prêt à publier,
- un email court,
- une idée de carrousel en 5 à 7 slides,
- un CTA.

IMPORTANT
- Ne copie aucune phrase de la source.
- Ne paraphrase pas ligne par ligne.
- Change les formulations, l'ordre, les exemples et l'angle si nécessaire.
- L'objectif est de créer une version originale inspirée de la mécanique, pas du contenu.

Réponds STRICTEMENT en JSON valide avec cette structure :
{{
  "analysis": {{
    "hook": "...",
    "angle": "...",
    "pain": "...",
    "desire": "...",
    "format": "...",
    "why_it_can_work": "...",
    "anti_copy_safety": "..."
  }},
  "generated": {{
    "post": "...",
    "email": "...",
    "carrousel": [
      {{"slide": 1, "title": "...", "body": "..."}}
    ],
    "cta": "..."
  }},
  "recommendation": "..."
}}
""".strip()


def analyze_and_transform_trend(
    *,
    source_text: str,
    source_url: Optional[str] = None,
    niche: str = "",
    audience: str = "",
    offer: str = "",
    objective: str = "",
    output_type: str = "post",
    tone: str = "premium, humain, direct",
) -> Dict[str, Any]:
    clean_source = _clean(source_text)
    clean_url = _clean(source_url)

    if not clean_source and not clean_url:
        raise ValueError("source_text ou source_url est requis.")

    source_for_prompt = clean_source
    if clean_url and not clean_source:
        source_for_prompt = (
            "L'utilisateur a fourni uniquement une URL. "
            "Ne prétends pas avoir lu la page. Analyse l'URL comme signal d'intention "
            "et demande le texte si nécessaire, tout en proposant une structure d'analyse exploitable."
        )

    prompt = _build_prompt(
        source_text=source_for_prompt,
        source_url=clean_url or None,
        niche=_clean(niche),
        audience=_clean(audience),
        offer=_clean(offer),
        objective=_clean(objective),
        output_type=_clean(output_type, "post"),
        tone=_clean(tone, "premium, humain, direct"),
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=_choose_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.68,
        max_tokens=1800,
    )

    content = ""
    try:
        content = (response.choices[0].message.content or "").strip()
    except Exception:
        content = ""

    if not content:
        raise RuntimeError("Réponse OpenAI vide pour Trend Radar.")

    data = _safe_json_loads(content)
    data["source"] = {
        "url": clean_url or None,
        "has_text": bool(clean_source),
        "mode": "analysis_transform_no_copy",
    }
    return data
