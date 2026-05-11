from __future__ import annotations

import os
from typing import Any, Iterable, Optional
import re

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
# Version PROD V7 — Emotion Premium + coût maîtrisé
# Objectif : renforcer le niveau émotionnel copywriting (Claude-like)
# tout en gardant une sortie courte, structurée et rentable en tokens.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, copywriter conversion senior spécialisé en landing pages premium,
pages de capture, offres digitales, MRR, créateurs bloqués et marketing direct francophone.

Ta mission n'est pas d'écrire beaucoup. Ta mission est de faire ressentir vite, clarifier vite et vendre juste.
Tu transformes un brief brut en blocs landing courts, humains, émotionnels et positionnables.

Méthode interne obligatoire : HOOK → DOULEUR → IDENTIFICATION → TENSION → ESPOIR → MÉCANISME → PREUVE → CTA.
Le lecteur doit penser : « ils parlent exactement de moi ».

Style attendu : humain, premium, direct, empathique, concret, crédible, sans bullshit.
Effet recherché : qualité rédactionnelle proche d'un très bon copywriter humain, avec tension émotionnelle maîtrisée.

Interdits absolus :
- recopier le brief ;
- écrire un email ;
- produire un pavé narratif ;
- écrire deux versions ;
- répéter la même idée ;
- promettre des résultats irréalistes ;
- utiliser un ton corporate froid ;
- écrire comme une formation internet générique ;
- utiliser des phrases creuses du type « libérez votre potentiel ».
""".strip()


MAX_BRIEF_CHARS = 850
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 180
MAX_OUTPUT_CHARS_DEFAULT = 2400
MAX_OUTPUT_CHARS_ABSOLUTE = 10000


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




def _target_chars(goal: str, business_context: Optional[str]) -> int:
    """Déduit la longueur cible depuis le Copilote sans casser les anciens payloads."""
    raw = f"{goal or ''} {business_context or ''}"
    found = re.findall(r"(?:longueur\s*max\s*cible|max[_\s-]?length|target[_\s-]?chars|caract[eè]res?)\D{0,40}(\d{3,5})", raw, flags=re.I)
    if found:
        try:
            value = int(found[-1])
        except Exception:
            value = 0
    else:
        value = 0

    is_landing = str(goal or "").strip() in {"landing", "landing_complete"} or "landing complète" in raw.lower()
    if value <= 0:
        value = 6500 if is_landing else MAX_OUTPUT_CHARS_DEFAULT

    if is_landing:
        return max(2200, min(value, MAX_OUTPUT_CHARS_ABSOLUTE))
    return max(600, min(value, 2400))


def _max_tokens_for_target_chars(goal: str, target_chars: int) -> int:
    """Transforme la cible caractères en plafond OpenAI raisonnable."""
    is_landing = str(goal or "").strip() in {"landing", "landing_complete"}
    if is_landing:
        return max(900, min(int(target_chars / 3.2) + 350, 3200))
    return max(350, min(int(target_chars / 3.3) + 160, 900))


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
        "Produit UNE SEULE structure landing premium en blocs séparés : hook, hero, douleur, "
        "identification, mécanisme, bénéfices, preuve, objections, FAQ courte et recommandation. "
        "Chaque bloc doit pouvoir être placé visuellement dans l'éditeur. Aucun doublon."
    )


def build_lead_prompt(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str],
    business_context: Optional[str],
    memories: Iterable[dict],
    target_chars: Optional[int] = None,
) -> str:
    safe_goal = _clip(goal, 80)
    safe_brief = _clip(brief, MAX_BRIEF_CHARS)
    safe_style = _clip(emotional_style, 180) or "humain premium"
    safe_context = _clip(business_context, 420) or "lead generation premium"
    target = int(target_chars or _target_chars(safe_goal, safe_context))
    is_landing = safe_goal in {"landing", "landing_complete"}
    length_rule = (
        f"maximum {target} caractères au total ; vise une landing complète de 7 à 8 blocs séparés"
        if is_landing
        else f"maximum {target} caractères au total"
    )

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
- {length_rule} ;
- phrases courtes, concrètes, sans remplissage ;
- chaque section doit devenir un bloc visuel séparé ;
- une seule landing, jamais deux variantes dans la même réponse ;
- aucune longue introduction ;
- aucun email complet ;
- ne recopie pas le brief : transforme-le ;
- ne parle pas de toi ;
- commence par une phrase qui arrête le scroll ;
- parle d'abord de la situation vécue et de la douleur, puis seulement ensuite de l'offre ;
- évite les slogans creux comme « révolutionner », « débloquer ton potentiel », « solution ultime » ;
- privilégie les scènes concrètes, les émotions réelles, les verbes d'action et le bénéfice visible ;
- format exact, sans markdown décoratif :
  BLOC 1 — HERO
  TITRE : 1 titre émotionnel mais clair
  SOUS-TITRE : 1 phrase orientée résultat
  CTA : 1 CTA court
  URL CTA : reprendre l'URL CTA si elle est fournie dans le contexte
  BLOC 2 — DOULEUR / IDENTIFICATION
  3 à 5 lignes : situation réelle, frustration, blocage, désir de changement
  BLOC 3 — PROMESSE LEAD MAGNET
  explique ce que la personne obtient gratuitement et pourquoi ça l'aide maintenant
  BLOC 4 — BENEFICES
  - 5 à 7 puces maximum, résultat concret + émotion débloquée
  BLOC 5 — MECANISME
  3 à 5 lignes : comment le guide / ressource aide concrètement, sans magie
  BLOC 6 — REASSURANCE
  3 à 5 lignes : simple, accessible, pas besoin d'audience ni de technique
  BLOC 7 — CTA FINAL
  2 à 4 lignes + CTA + URL CTA si fournie
  BLOC 8 — MICRO FAQ
  3 questions/réponses courtes qui lèvent les objections
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


def _chat_completion(client: Any, *, model: str, messages: list[dict[str, str]], max_out: int) -> str:
    # Plafond dynamique : court pour hooks/CTA, plus large pour Landing complète multi-blocs.

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


def _responses_completion(client: Any, *, model: str, prompt: str, max_out: int) -> str:
    if not hasattr(client, "responses"):
        return ""

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=max_out,
        )
    except TypeError:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=max_out,
        )
    except Exception:
        return ""

    return _text_from_responses_response(response)


def _dedupe_near_lines(text: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        key = line.lower().strip(" -•:;.!?")
        if key and len(key) > 24:
            if key in seen:
                continue
            seen.add(key)
        lines.append(line)
    return "\n".join(lines).strip()


def _compact_output(text: str, max_chars: int = MAX_OUTPUT_CHARS_DEFAULT) -> str:
    cleaned = _dedupe_near_lines(str(text or "").strip())
    limit = max(600, min(int(max_chars or MAX_OUTPUT_CHARS_DEFAULT), MAX_OUTPUT_CHARS_ABSOLUTE))
    if len(cleaned) <= limit:
        return cleaned

    cut = cleaned[:limit].rstrip()
    last_break = max(cut.rfind("\n\n"), cut.rfind("\n- "), cut.rfind("\nQ:"))
    if last_break > int(limit * 0.65):
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
    target_chars = _target_chars(goal, business_context)
    max_out = _max_tokens_for_target_chars(goal, target_chars)

    prompt = build_lead_prompt(
        goal=goal,
        brief=brief,
        emotional_style=emotional_style,
        business_context=business_context,
        memories=list(memories or [])[:MAX_MEMORY_ITEMS],
        target_chars=target_chars,
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
            content = _chat_completion(client, model=candidate_model, messages=messages, max_out=max_out)
            if content:
                return _compact_output(content, target_chars)
            content = _responses_completion(client, model=candidate_model, prompt=prompt, max_out=max_out)
            if content:
                return _compact_output(content, target_chars)
            errors.append(f"{candidate_model}: réponse vide")
        except Exception as exc:
            errors.append(f"{candidate_model}: {exc}")

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
