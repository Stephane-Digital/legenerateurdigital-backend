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


# ============================================================
# LGD — Lead Engine IA
# Version PROD V4 — économie + qualité landing
# Objectif : conserver une réponse premium exploitable tout en divisant
# fortement la consommation de tokens côté OpenAI et côté quotas LGD.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, expert senior en landing pages courtes, pages de vente SIO,
lead magnets et conversion.

Tu ne rédiges PAS un email complet.
Tu ne recopies PAS le brief.
Tu transformes le brief en blocs landing courts, directement injectables dans une page.

Style : français naturel, premium, direct, émotionnel mais maîtrisé.
Objectif : clarté, conversion, action. Zéro remplissage.
""".strip()


MAX_BRIEF_CHARS = 900
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 220
MAX_OUTPUT_CHARS = 2400


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
    # Modèle économique par défaut : le Lead Engine doit rester rentable en PROD.
    return (
        _setting("OPENAI_LEAD_ENGINE_MODEL")
        or "gpt-4o-mini"
    )


def _fallback_model(primary_model: str) -> str:
    configured = _setting("OPENAI_LEAD_ENGINE_FALLBACK_MODEL") or _setting("OPENAI_FALLBACK_MODEL")
    if configured and configured != primary_model:
        return configured
    if primary_model.lower() != "gpt-4o-mini":
        return "gpt-4o-mini"
    return "gpt-4o-mini"


def _clip(value: Optional[str], limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _memory_block(memories: Iterable[dict]) -> str:
    lines: list[str] = []

    for item in list(memories or [])[:MAX_MEMORY_ITEMS]:
        memory_type = str(item.get("memory_type") or "memoire")[:40]
        goal = _clip(str(item.get("goal") or ""), 90)
        content = _clip(str(item.get("content") or ""), MAX_MEMORY_CHARS)
        business = _clip(str(item.get("business_context") or ""), 110)

        if not content:
            continue

        line = f"- {memory_type}"
        if goal:
            line += f" | objectif={goal}"
        if business:
            line += f" | contexte={business}"
        line += f" | contenu={content}"
        lines.append(line)

    if not lines:
        return "Aucune mémoire utile."

    return "\n".join(lines)


def _goal_instruction(goal: str) -> str:
    value = str(goal or "landing_complete")

    if value == "hooks":
        return "Produit 6 hooks landing très courts. Format : Hook + intention. Maximum 12 mots par hook."
    if value == "cta":
        return "Produit 8 CTA courts classés doux / direct / urgent. Maximum 8 mots par CTA."
    if value == "benefits":
        return "Produit 6 bénéfices courts : résultat concret + émotion débloquée. Pas de paragraphe."
    if value == "variants":
        return "Produit 3 angles A/B/C ultra courts : promesse, douleur, CTA."
    if value == "rewrite_landing":
        return "Réécris le contenu en version landing plus courte, plus nette, sans ajouter de longueur."

    return (
        "Produit UNE SEULE structure landing en blocs séparés : hero, 5 bénéfices, "
        "mécanisme, preuve, objections, CTA, FAQ courte. Aucun doublon."
    )


def build_lead_prompt(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str],
    business_context: Optional[str],
    memories: Iterable[dict],
) -> str:
    safe_goal = _clip(goal, 80)
    safe_brief = _clip(brief, MAX_BRIEF_CHARS)
    safe_style = _clip(emotional_style, 180) or "humain premium"
    safe_context = _clip(business_context, 240) or "lead generation premium"

    return f"""
Objectif : {safe_goal}

Brief utilisateur :
{safe_brief}

Style : {safe_style}
Contexte : {safe_context}

Mémoire utile :
{_memory_block(memories)}

Mission :
{_goal_instruction(safe_goal)}

Contraintes de sortie obligatoires :
- maximum 450 mots ;
- chaque section doit pouvoir devenir un bloc visuel séparé ;
- jamais deux versions de la même landing ;
- jamais de pavé narratif ;
- jamais d'email complet ;
- ne recopie pas le brief ;
- blocs courts directement utilisables dans la landing ;
- format exact :
  HERO
  TITRE : 1 titre court et puissant
  SOUS-TITRE : 1 phrase claire
  CTA PRINCIPAL : 1 CTA court
  BENEFICES
  - 5 puces maximum
  MECANISME
  3 à 5 lignes maximum
  PREUVE / RASSURANCE
  3 à 4 lignes maximum
  OBJECTIONS
  - 4 objections + réponses courtes maximum
  FAQ COURTE
  Q: question courte
  R: réponse courte
  A UTILISER EN PRIORITE
  1 recommandation courte
""".strip()


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
    # Plafond volontairement bas : assez pour une sortie premium compacte,
    # pas assez pour brûler 7k à 15k tokens par génération.
    max_out = 360

    try:
        if model.lower().startswith("gpt-5"):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_out,
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.55,
                max_tokens=max_out,
            )
    except TypeError:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_out,
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "max_tokens" in error_text or "temperature" in error_text or "unsupported" in error_text:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_out,
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
            max_output_tokens=360,
        )
    except TypeError:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=360,
        )
    except Exception:
        return ""

    return _text_from_responses_response(response)


def _compact_output(text: str) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= MAX_OUTPUT_CHARS:
        return cleaned

    cut = cleaned[:MAX_OUTPUT_CHARS].rstrip()
    last_break = max(cut.rfind("\n\n"), cut.rfind("\n- "), cut.rfind("\nQ:"))
    if last_break > 1800:
        cut = cut[:last_break].rstrip()
    return cut + "\n\nA UTILISER EN PRIORITE\nLa version courte ci-dessus pour éviter une landing trop longue."


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
        memories=list(memories or [])[:MAX_MEMORY_ITEMS],
    )

    model = _choose_model()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    errors: list[str] = []
    candidate_models = [model]
    fallback = _fallback_model(model)
    if fallback not in candidate_models:
        candidate_models.append(fallback)

    for candidate_model in candidate_models:
        try:
            content = _chat_completion(client, model=candidate_model, messages=messages)
            if content:
                return _compact_output(content)
            content = _responses_completion(client, model=candidate_model, prompt=prompt)
            if content:
                return _compact_output(content)
            errors.append(f"{candidate_model}: réponse vide")
        except Exception as exc:
            errors.append(f"{candidate_model}: {exc}")

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
