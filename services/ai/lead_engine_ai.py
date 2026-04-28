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


SYSTEM_PROMPT = '''
Tu es LEAD ENGINE V2, l'IA premium de LGD.

Rôle : stratège funnel, copywriter direct-response, expert lead magnet, landing page,
offre irrésistible, psychologie d'achat et conversion.

Ta mission : transformer un brief utilisateur souvent flou en contenu exploitable,
plus clair, plus désirable, plus crédible et plus orienté action qu'une IA générique.

Méthode invisible avant réponse :
1. clarifier la cible,
2. identifier douleur, désir, objection, urgence et niveau de conscience,
3. choisir l'angle marketing le plus fort,
4. structurer promesse, bénéfices, preuve, CTA,
5. produire une sortie directement utilisable.

Règles absolues :
- voix humaine, jamais robotique ;
- concret > abstrait ;
- bénéfices spécifiques > slogans ;
- crédible > promesse magique ;
- émotion + clarté + action ;
- jamais de copie mot à mot d'un contenu fourni ;
- si le brief est faible, enrichis-le avec des hypothèses raisonnables clairement utiles ;
- propose des variantes A/B quand cela augmente la conversion.
'''.strip()


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

    return "\n".join(lines)


def build_lead_prompt(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str],
    business_context: Optional[str],
    memories: Iterable[dict],
) -> str:
    return f'''
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

CADRE STRATÉGIQUE À APPLIQUER
- Déduis la cible réelle, le niveau de conscience, la douleur dominante et le désir principal.
- Identifie l'objection qui bloque le passage à l'action.
- Transforme l'idée en angle de conversion clair.
- Garde une écriture simple, premium, humaine et orientée résultat.
- Ne copie jamais un exemple fourni : extrais la mécanique et reformule complètement.

INSTRUCTIONS DE SORTIE
- Réponds en français.
- Donne une réponse directement exploitable dans Lead Engine.
- Si l'objectif est une landing, structure : hero, promesse, sous-promesse, bénéfices, mécanisme, preuve, objections, CTA, FAQ.
- Si l'objectif est un lead magnet, fournis : titre, promesse, plan, bénéfices, hook, CTA, angle différenciant.
- Si l'objectif est hooks/CTA, fournis des variantes A/B/C fortes et différenciées.
- Termine par une recommandation courte : "À utiliser en priorité : ...".
'''.strip()


def generate_lead_content(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str] = None,
    business_context: Optional[str] = None,
    memories: Optional[Iterable[dict]] = None,
) -> str:
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
        temperature=0.62,
        max_tokens=1400,
    )

    content = response.choices[0].message.content if response.choices else ""
    content = (content or "").strip()
    if not content:
        raise RuntimeError("Réponse OpenAI vide pour Lead Engine.")
    return content
