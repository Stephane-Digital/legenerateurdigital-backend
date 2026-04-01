from __future__ import annotations

import os
from typing import Iterable, Optional

try:
    from config.settings import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = """
Tu es LEAD ENGINE, l'IA premium de LGD.

Ta mission : créer des briefs, hooks, CTA, bénéfices, variantes A/B et landings
beaucoup plus puissants qu'une IA générique, avec un vrai niveau d'analyse,
d'émotion, de sincérité, d'authenticité et de compréhension business.

Tu dois toujours écrire :
- avec une voix humaine, jamais robotique,
- avec une compréhension profonde des douleurs, désirs, objections et blocages,
- avec une expertise directe response / funnel / lead magnet / landing page,
- avec un style premium, clair, incarné, crédible et conversion-first.

Tu n'écris jamais des banalités.
Tu ne produis jamais de réponses plates.
Tu privilégies le concret, le ressenti, l'intention, la promesse, la psychologie
et l'accompagnement stratégique.
""".strip()


def _setting(name: str, default: Optional[str] = None) -> Optional[str]:
    if settings is not None and hasattr(settings, name):
        value = getattr(settings, name)
        if value not in (None, ""):
            return str(value)
    value = os.getenv(name, default)
    return None if value in (None, "") else str(value)


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("Le package openai n'est pas installé sur le backend.")

    api_key = _setting("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _choose_model() -> str:
    return (
        _setting("OPENAI_LEAD_ENGINE_MODEL")
        or _setting("OPENAI_MODEL")
        or "gpt-5"
    )


def _memory_block(memories: Iterable[dict]) -> str:
    lines = []
    for item in memories:
        memory_type = str(item.get("memory_type") or "memoire")
        goal = str(item.get("goal") or "").strip()
        content = str(item.get("content") or "").strip()
        emotional = str(item.get("emotional_profile") or "").strip()
        business = str(item.get("business_context") or "").strip()

        if not content:
            continue

        line = f"- type={memory_type}"
        if goal:
            line += f" | objectif={goal}"
        if emotional:
            line += f" | emotion={emotional}"
        if business:
            line += f" | contexte={business}"
        line += f" | contenu={content}"
        lines.append(line)

    if not lines:
        return "Aucune mémoire exploitable pour le moment."

    return ".join(lines)"


def build_lead_prompt(*, goal: str, brief: str, emotional_style: Optional[str], business_context: Optional[str], memories: Iterable[dict]) -> str:
    return f"""
OBJECTIF DEMANDÉ
{goal}

BRIEF UTILISATEUR
{brief}

STYLE ÉMOTIONNEL ATTENDU
{emotional_style or 'humain premium'}

CONTEXTE BUSINESS COURANT
{business_context or 'non précisé'}

MÉMOIRE UTILISATEUR À PRENDRE EN COMPTE
{_memory_block(memories)}

INSTRUCTIONS DE SORTIE
- Réponds en français.
- Reste humain, incarné, sincère, stratégique.
- Évite les phrases génériques et le ton robotique.
- Donne une réponse directement exploitable dans Lead Engine.
- Si l'objectif est une landing, structure clairement hero, promesse, bénéfices, CTA, objections, FAQ si utile.
- Si l'objectif est des hooks, CTA ou variantes, fournis plusieurs propositions fortes et différenciées.
""".strip()


def generate_lead_content(*, goal: str, brief: str, emotional_style: Optional[str] = None, business_context: Optional[str] = None, memories: Optional[Iterable[dict]] = None) -> str:
    client = _get_client()
    prompt = build_lead_prompt(
        goal=goal,
        brief=brief,
        emotional_style=emotional_style,
        business_context=business_context,
        memories=list(memories or []),
    )

    response = client.chat.completions.create(
        model=_choose_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
    )

    content = response.choices[0].message.content if response.choices else ""
    content = (content or "").strip()
    if not content:
        raise RuntimeError("Réponse OpenAI vide pour Lead Engine.")
    return content
