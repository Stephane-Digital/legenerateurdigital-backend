from __future__ import annotations

import os
from typing import Any, Iterable, Optional

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
- propose des variantes A/B quand cela augmente la conversion ;
- ajoute systématiquement un angle principal recommandé et explique brièvement pourquoi il est prioritaire ;
- si possible, propose une version "simple débutant" et une version "premium avancée".
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
        or "gpt-4o-mini"
    )


def _fallback_model(primary_model: str) -> str:
    configured = _setting("OPENAI_LEAD_ENGINE_FALLBACK_MODEL") or _setting("OPENAI_FALLBACK_MODEL")
    if configured and configured != primary_model:
        return configured
    if primary_model.lower() != "gpt-4o-mini":
        return "gpt-4o-mini"
    return "gpt-4o"


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
- Ajoute une mini-section "Pourquoi cet angle peut convertir" en 2 lignes maximum.
'''.strip()


def _text_from_chat_response(response: Any) -> str:
    try:
        if not getattr(response, "choices", None):
            return ""
        message = response.choices[0].message
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    value = item.get("text") or item.get("content") or ""
                    if isinstance(value, dict):
                        value = value.get("value") or value.get("text") or ""
                    if value:
                        parts.append(str(value))
                else:
                    value = getattr(item, "text", None) or getattr(item, "content", None) or ""
                    if value:
                        parts.append(str(value))
            return "\n".join(parts).strip()
    except Exception:
        return ""
    return ""


def _text_from_responses_response(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    try:
        for output in getattr(response, "output", []) or []:
            for content in getattr(output, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(str(text))
    except Exception:
        pass

    return "\n".join(parts).strip()


def _chat_completion(client: Any, *, model: str, messages: list[dict[str, str]]) -> str:
    try:
        if model.lower().startswith("gpt-5"):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=4200,
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.62,
                max_tokens=2200,
            )
    except TypeError:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2200,
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "max_tokens" in error_text or "temperature" in error_text or "unsupported" in error_text:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=4200,
            )
        else:
            raise

    return _text_from_chat_response(response)


def _responses_completion(client: Any, *, model: str, prompt: str) -> str:
    if not hasattr(client, "responses"):
        return ""

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=2600,
        )
    except TypeError:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=2600,
        )
    except Exception:
        return ""

    return _text_from_responses_response(response)


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

    model = _choose_model()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    errors: list[str] = []

    for candidate_model in [model, _fallback_model(model)]:
        try:
            content = _chat_completion(client, model=candidate_model, messages=messages)
            if content:
                return content
            content = _responses_completion(client, model=candidate_model, prompt=prompt)
            if content:
                return content
            errors.append(f"{candidate_model}: réponse vide")
        except Exception as exc:
            errors.append(f"{candidate_model}: {exc}")

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
