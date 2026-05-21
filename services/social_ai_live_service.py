from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class SocialAILiveError(RuntimeError):
    pass


# Rôles autorisés pour les blocs de contenu
ALLOWED_ROLES = {"hook", "body", "cta", "slide", "title"}

# Expressions "gourou" et verbeuses à proscrire absolument
FORBIDDEN_WEAK_PHRASES = [
    "vous méritez",
    "croyez en vous",
    "crois en toi",
    "passez à l'action",
    "passe à l'action",
    "connectez-vous avec votre audience",
    "écoutez votre audience",
    "ecoutez votre audience",
    "contenu authentique",
    "authenticité",
    "apportez de la valeur",
    "apporter de la valeur",
    "il est essentiel",
    "dans le monde d'aujourd'hui",
    "découvrez comment",
    "decouvrez comment",
    "optimisez votre stratégie",
    "optimisez votre strategie",
    "comprenez ses besoins",
    "comprenez leurs besoins",
    "résultats concrets",
    "resultats concrets",
    "votre potentiel",
    "libérez votre potentiel",
    "transformez votre vie",
    "boostez votre présence",
    "stratégie gagnante",
    "interagis avec ta communauté",
    "fais preuve de transparence",
    "la confiance se construit",
    "ne cherche pas à tout faire",
    "avance pas à pas",
]

# Jetons d'identification pour la niche MRR / Produits digitaux
MRR_TOKENS = [
    "mrr",
    "master resale",
    "produit digital",
    "produits digitaux",
    "formation",
    "formations",
    "affiliation",
    "revente",
]

# Signaux pour la structure d'interruption ("arrête de")
STOP_TOKENS = [
    "arrête",
    "arrete",
    "stop",
    "doit arrêter",
    "doit arreter",
    "arrêter de faire",
    "arreter de faire",
    "stop doing",
]


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").replace("\r", "").strip()
    return text or fallback


def _clip(value: Any, limit: int = 2800) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise SocialAILiveError("Le package openai n'est pas installé sur le backend.")

    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or "").strip()
    if not api_key:
        raise SocialAILiveError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _model() -> str:
    return (
        os.getenv("OPENAI_MODEL_SOCIAL_AI", "").strip()
        or os.getenv("OPENAI_MODEL_SOCIAL", "").strip()
        or os.getenv("OPENAI_MODEL_TEXT", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _all_context(payload: Dict[str, Any]) -> str:
    return " ".join(
        _clean(payload.get(key))
        for key in [
            "format",
            "network",
            "goal",
            "objective",
            "category",
            "tone",
            "prompt",
            "brief",
            "context",
            "offer",
            "product",
            "subject",
            "audience",
            "target",
            "pain",
            "promise",
            "result",
            "objection",
            "cta",
        ]
    ).lower()


def _is_mrr(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in MRR_TOKENS)


def _wants_stop_doing(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in STOP_TOKENS)


def _extract_json(raw: str) -> Dict[str, Any]:
    text = _clean(raw)
    text = re.sub(r"^
