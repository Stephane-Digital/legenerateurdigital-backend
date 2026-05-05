from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI

client = OpenAI()


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _extract_json(raw: str) -> Dict[str, Any]:
    text = _clean_text(raw)

    # Supprime les fences markdown si le modèle en ajoute malgré la consigne.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Récupération robuste si le modèle ajoute du texte autour du JSON.
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return {
        "titre": "Post IA",
        "contenu": text,
        "hashtags": [],
    }


def _normalize_hashtags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    hashtags: List[str] = []
    for item in value:
        tag = str(item or "").strip()
        if not tag:
            continue
        tag = tag.replace(" ", "")
        if not tag.startswith("#"):
            tag = f"#{tag}"
        hashtags.append(tag)

    # Déduplication stable.
    seen = set()
    clean: List[str] = []
    for tag in hashtags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            clean.append(tag)

    return clean[:10]


async def generate_social_text(
    reseau: str,
    format: str,
    objectif: str,
    ton: str,
    langue: str,
    prompt: str,
):
    """
    Générateur IA officiel LGD pour posts réseaux sociaux.
    Optimisé pour produire un contenu professionnel, humanisé, personnalisé et exploitable.
    """

    reseau_txt = _clean_text(reseau, "réseau social")
    format_txt = _clean_text(format, "post")
    objectif_txt = _clean_text(objectif, "engager et convertir")
    ton_txt = _clean_text(ton, "premium, humain, direct")
    langue_txt = _clean_text(langue, "fr")
    user_context = _clean_text(prompt, "Contexte utilisateur non précisé.")

    full_prompt = f"""
Tu es l'IA Social Media premium de Le Générateur Digital (LGD).

MISSION
Génère UN SEUL post social media prêt à publier.

CONTEXTE
- Réseau : {reseau_txt}
- Format : {format_txt}
- Objectif : {objectif_txt}
- Ton : {ton_txt}
- Langue : {langue_txt}

CONTEXTE UTILISATEUR
{user_context}

RÈGLES LGD
- Le post doit être spécifique au contexte utilisateur.
- Interdit de produire un post générique applicable à n'importe quelle offre.
- Le hook doit être concret et direct.
- Le texte doit être humain, fluide, premium et orienté conversion.
- Pas de ton corporate.
- Pas de promesse irréaliste.
- Pas de phrases IA classiques.
- Maximum 2 à 3 lignes par bloc.
- Si tu utilises le tutoiement, garde le tutoiement partout.
- Si tu utilises le vouvoiement, garde le vouvoiement partout.
- Par défaut, privilégie le tutoiement sauf si le contexte impose le vouvoiement.

STRUCTURE DU CONTENU
1. Hook court et percutant
2. Problème ou tension réelle
3. Déclic / valeur utile
4. Projection ou bénéfice concret
5. Fin naturelle avec CTA discret si utile

FORMAT JSON STRICT
Réponds uniquement avec ce JSON valide, sans markdown, sans commentaire :

{{
  "titre": "...",
  "contenu": "...",
  "hashtags": ["#exemple", "#exemple2"]
}}

RAPPEL FINAL
Aucun texte avant ou après le JSON.
""".strip()

    model = (
        os.getenv("OPENAI_MODEL_SOCIAL", "").strip()
        or os.getenv("OPENAI_MODEL_TEXT", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es l'IA Social Media premium de LGD. "
                    "Tu respectes strictement le JSON demandé. "
                    "Tu écris des contenus humains, spécifiques, crédibles et orientés conversion. "
                    "Tu évites les formulations génériques et les mélanges de pronom."
                ),
            },
            {"role": "user", "content": full_prompt},
        ],
        max_tokens=700,
        temperature=0.82,
        top_p=0.9,
        frequency_penalty=0.35,
        presence_penalty=0.25,
    )

    raw = completion.choices[0].message.content or ""
    data = _extract_json(raw)

    return {
        "titre": _clean_text(data.get("titre"), "Post IA"),
        "contenu": _clean_text(data.get("contenu"), raw),
        "hashtags": _normalize_hashtags(data.get("hashtags")),
    }
