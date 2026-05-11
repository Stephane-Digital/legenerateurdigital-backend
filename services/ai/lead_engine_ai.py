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
# Version PROD V8 — Copilote réellement branché
# Objectif : utiliser enfin objective / angle / audience / tone /
# max_length / cta_url / page_type pour générer des blocs Lead Magnet
# ou Landing selon l'intention réelle, sans exploser les tokens.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, copywriter conversion senior spécialisé en lead magnets,
pages de capture, landing pages premium, offres digitales, MRR, créateurs bloqués
et marketing direct francophone.

Ta mission n'est pas d'écrire beaucoup. Ta mission est de faire ressentir vite,
clarifier vite et déclencher une action mesurable.

Règle stratégique majeure :
- si l'objectif est de générer des leads, tu écris une page de capture / lead magnet ;
- tu ne vends pas directement la formation ;
- tu vends l'envie de laisser son email pour obtenir une micro-transformation rapide ;
- si l'objectif est vente, webinar, rendez-vous ou bridge page, tu adaptes la structure.

Méthode interne : HOOK → DOULEUR → IDENTIFICATION → CURIOSITÉ → MICRO-PROMESSE →
MÉCANISME SIMPLE → RÉASSURANCE → CTA EMAIL.
Le lecteur doit penser : « ils parlent exactement de moi » puis « je veux recevoir ça ».

Style attendu : humain, premium, direct, empathique, concret, crédible, sans bullshit.

Interdits absolus :
- ignorer les options du Copilote ;
- recopier le brief ;
- écrire un email ;
- produire un pavé narratif ;
- écrire deux versions ;
- répéter la même idée ;
- promettre des résultats irréalistes ;
- vendre agressivement une formation quand l'objectif est la capture email ;
- utiliser un ton corporate froid ;
- écrire comme une formation internet générique ;
- utiliser des slogans creux du type « libérez votre potentiel ».
""".strip()


MAX_BRIEF_CHARS = 950
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 140
MAX_OUTPUT_CHARS = 2600


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
    return _setting("OPENAI_LEAD_ENGINE_MODEL") or "gpt-4o-mini"


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


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _safe_int(value: Optional[int], default: int = 120) -> int:
    try:
        n = int(value) if value is not None else default
    except Exception:
        n = default
    return max(40, min(n, 1200))


def _memory_block(memories: Iterable[dict]) -> str:
    lines: list[str] = []

    for item in list(memories or [])[:MAX_MEMORY_ITEMS]:
        memory_type = str(item.get("memory_type") or "memoire")[:40]
        goal = _clip(str(item.get("goal") or ""), 70)
        content = _clip(str(item.get("content") or ""), MAX_MEMORY_CHARS)
        business = _clip(str(item.get("business_context") or ""), 80)

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


def _infer_page_type(goal: str, objective: Optional[str], page_type: Optional[str]) -> str:
    raw = " ".join([_norm(goal), _norm(objective), _norm(page_type)])

    if any(word in raw for word in ["lead", "email", "capture", "prospect", "magnet"]):
        return "lead_magnet"
    if any(word in raw for word in ["webinar", "atelier", "masterclass"]):
        return "webinar"
    if any(word in raw for word in ["rdv", "rendez", "appel", "call", "diagnostic"]):
        return "appointment"
    if any(word in raw for word in ["bridge", "transition", "prévente", "prevente"]):
        return "bridge"
    if any(word in raw for word in ["vente", "vendre", "achat", "payer", "commande"]):
        return "sales"
    return "lead_magnet" if _norm(goal) == "landing_complete" else "modular"


def _page_strategy(page_type: str) -> str:
    if page_type == "lead_magnet":
        return (
            "TYPE DE PAGE : LEAD MAGNET / CAPTURE EMAIL. Priorité absolue : récupérer l'email. "
            "Ne cherche pas à vendre directement l'offre principale. Crée de la curiosité, une micro-promesse "
            "rapide, une faible friction et un CTA d'inscription."
        )
    if page_type == "webinar":
        return (
            "TYPE DE PAGE : WEBINAR / MASTERCLASS. Priorité : inscription. Promets une prise de conscience forte, "
            "un apprentissage concret et une raison claire d'assister."
        )
    if page_type == "appointment":
        return (
            "TYPE DE PAGE : PRISE DE RENDEZ-VOUS. Priorité : réserver un diagnostic. Rassure, qualifie, "
            "montre le bénéfice de l'appel et limite la friction."
        )
    if page_type == "bridge":
        return (
            "TYPE DE PAGE : BRIDGE PAGE. Priorité : faire passer d'une prise de conscience à l'étape suivante. "
            "Crée confiance, contexte et transition."
        )
    if page_type == "sales":
        return (
            "TYPE DE PAGE : LANDING DE VENTE. Priorité : désir + confiance + passage à l'achat. "
            "Reste crédible, sans promesses irréalistes."
        )
    return "TYPE DE SORTIE : MODULE COURT. Réponds uniquement au bouton demandé."


def _copilot_options_block(
    *,
    objective: Optional[str],
    angle: Optional[str],
    audience: Optional[str],
    tone: Optional[str],
    max_length: int,
    cta_url: Optional[str],
    page_type: str,
) -> str:
    return f"""
OPTIONS COPILOTE À RESPECTER STRICTEMENT :
- Objectif sélectionné : {_clip(objective, 90) or "Générer des leads"}
- Type de page déduit : {page_type}
- Angle sélectionné : {_clip(angle, 90) or "Angle conversion clair"}
- Audience sélectionnée : {_clip(audience, 120) or "Audience froide ou tiède"}
- Ton / style sélectionné : {_clip(tone, 90) or "Humain premium"}
- Longueur max UI : {max_length}
- URL CTA : {_clip(cta_url, 220) or "Non fournie"}

Ces options ne sont pas décoratives : elles doivent piloter le vocabulaire, le niveau d'émotion,
le type de promesse, la longueur et le CTA final.
""".strip()


def _goal_instruction(goal: str, page_type: str, max_length: int) -> str:
    value = str(goal or "landing_complete")

    if value == "hooks":
        return (
            f"Produit 10 hooks pour {page_type}. Chaque hook doit faire {min(max_length, 120)} caractères maximum. "
            "Format : HOOK 1: ..."
        )
    if value == "cta":
        return (
            f"Produit 10 CTA courts pour {page_type}. Chaque CTA doit faire {min(max_length, 80)} caractères maximum. "
            "Classe-les en doux / direct / émotionnel."
        )
    if value == "benefits":
        return (
            "Produit 8 bénéfices courts. Chaque bénéfice = résultat concret + émotion débloquée. "
            f"Maximum {min(max_length, 140)} caractères par puce."
        )
    if value == "variants":
        return (
            f"Produit 3 variantes A/B/C pour {page_type}. Pour chaque variante : hook, micro-promesse, CTA. "
            f"Maximum {min(max_length, 180)} caractères par ligne."
        )
    if value == "rewrite_landing":
        return (
            "Réécris le contenu fourni en blocs plus courts, mieux structurés, plus orientés capture email si l'objectif est lead. "
            "Ne rajoute pas de longueur."
        )

    if page_type == "lead_magnet":
        return (
            "Produit UNE structure Lead Magnet en blocs séparés et injectables dans le canvas. "
            "Objectif : inscription email maximale, pas vente directe."
        )

    return (
        f"Produit UNE structure {page_type} premium en blocs séparés et injectables dans le canvas. "
        "Aucun doublon, aucun pavé."
    )


def _format_rules(page_type: str, max_length: int, cta_url: Optional[str]) -> str:
    line_limit = min(max_length, 160)

    if page_type == "lead_magnet":
        return f"""
FORMAT EXACT OBLIGATOIRE, SANS MARKDOWN DÉCORATIF :
BLOC 1 — HERO
TITRE: 1 phrase émotionnelle, {line_limit} caractères max
SOUS-TITRE: micro-promesse gratuite, {line_limit} caractères max
CTA: appel à laisser son email, 70 caractères max
URL CTA: {_clip(cta_url, 220) or "à renseigner"}

BLOC 2 — IDENTIFICATION
3 puces maximum : situation vécue, frustration, envie de changement

BLOC 3 — CE QUE TU VAS RECEVOIR
4 puces maximum : contenu gratuit, résultat rapide, clarté gagnée, prochaine action

BLOC 4 — POURQUOI ÇA DÉBLOQUE
3 lignes maximum : mécanisme simple, pas de magie, action concrète

BLOC 5 — RÉASSURANCE
3 puces maximum : pas besoin d'audience, pas besoin d'être expert, pas de promesse fake

BLOC 6 — CTA FINAL
1 phrase courte de transition + 1 CTA email

BLOC 7 — MICRO FAQ
2 questions / réponses maximum

BLOC PRIORITAIRE À INJECTER
Indique le bloc qui doit être placé au-dessus de la ligne de flottaison.
""".strip()

    return f"""
FORMAT EXACT OBLIGATOIRE, SANS MARKDOWN DÉCORATIF :
BLOC 1 — HERO
TITRE: {line_limit} caractères max
SOUS-TITRE: {line_limit} caractères max
CTA: 70 caractères max
URL CTA: {_clip(cta_url, 220) or "à renseigner"}

BLOC 2 — DOULEUR
3 puces maximum

BLOC 3 — PROMESSE
3 puces maximum

BLOC 4 — MÉCANISME
3 lignes maximum

BLOC 5 — PREUVE / RASSURANCE
3 puces maximum

BLOC 6 — CTA FINAL
1 phrase + 1 CTA

BLOC PRIORITAIRE À INJECTER
1 recommandation courte.
""".strip()


def build_lead_prompt(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str],
    business_context: Optional[str],
    memories: Iterable[dict],
    objective: Optional[str] = None,
    angle: Optional[str] = None,
    audience: Optional[str] = None,
    tone: Optional[str] = None,
    max_length: Optional[int] = None,
    cta_url: Optional[str] = None,
    page_type: Optional[str] = None,
) -> str:
    safe_goal = _clip(goal, 80)
    safe_brief = _clip(brief, MAX_BRIEF_CHARS)
    safe_style = _clip(emotional_style, 160) or "humain premium"
    safe_context = _clip(business_context, 220) or "lead generation premium"
    safe_max_length = _safe_int(max_length, 120)
    inferred_page_type = _infer_page_type(safe_goal, objective, page_type)

    return f"""
Objectif interne : {safe_goal}

{_page_strategy(inferred_page_type)}

{_copilot_options_block(
    objective=objective,
    angle=angle,
    audience=audience,
    tone=tone,
    max_length=safe_max_length,
    cta_url=cta_url,
    page_type=inferred_page_type,
)}

Brief utilisateur :
{safe_brief}

Style complémentaire : {safe_style}
Contexte métier : {safe_context}

Mémoire utile :
{_memory_block(memories)}

Mission :
{_goal_instruction(safe_goal, inferred_page_type, safe_max_length)}

Contraintes de sortie obligatoires :
- respecte strictement objectif, angle, audience, ton, longueur et URL CTA ;
- si Objectif = générer des leads, écris pour capturer un email, pas pour vendre directement ;
- chaque section doit être un bloc visuel séparé positionnable dans l'éditeur ;
- pas de pavé ;
- phrases courtes ;
- une seule version ;
- aucune longue introduction ;
- ne recopie pas le brief : transforme-le ;
- ne parle pas de toi ;
- commence par une phrase qui arrête le scroll ;
- parle d'abord de la situation vécue et de la douleur, puis de la micro-promesse ;
- évite « révolutionner », « libérez votre potentiel », « solution ultime » ;
- utilise le vocabulaire de l'audience sélectionnée ;
- si l'angle mentionne MRR, parle de formations achetées, d'inaction, de première vente, de dispersion, sans caricature ;
- si le ton est storytelling, ajoute une micro-scène concrète sans allonger.

{_format_rules(inferred_page_type, safe_max_length, cta_url)}
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
    max_out = 520

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
                temperature=0.52,
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
            max_output_tokens=520,
        )
    except TypeError:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=520,
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


def _compact_output(text: str) -> str:
    cleaned = _dedupe_near_lines(str(text or "").strip())
    if len(cleaned) <= MAX_OUTPUT_CHARS:
        return cleaned

    cut = cleaned[:MAX_OUTPUT_CHARS].rstrip()
    last_break = max(cut.rfind("\n\nBLOC"), cut.rfind("\nBLOC"), cut.rfind("\n- "))
    if last_break > 1700:
        cut = cut[:last_break].rstrip()
    return cut + "\n\nBLOC PRIORITAIRE À INJECTER\nConserve la version courte ci-dessus pour éviter une page trop longue."


def generate_lead_content(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str] = None,
    business_context: Optional[str] = None,
    memories: Optional[Iterable[dict]] = None,
    objective: Optional[str] = None,
    angle: Optional[str] = None,
    audience: Optional[str] = None,
    tone: Optional[str] = None,
    max_length: Optional[int] = None,
    cta_url: Optional[str] = None,
    page_type: Optional[str] = None,
) -> str:
    client = _get_client()
    prompt = build_lead_prompt(
        goal=goal,
        brief=brief,
        emotional_style=emotional_style,
        business_context=business_context,
        memories=list(memories or [])[:MAX_MEMORY_ITEMS],
        objective=objective,
        angle=angle,
        audience=audience,
        tone=tone,
        max_length=max_length,
        cta_url=cta_url,
        page_type=page_type,
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
