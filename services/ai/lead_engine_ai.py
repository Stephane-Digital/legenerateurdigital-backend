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
# Version PROD V8.8 — Lead Magnet Blocks + plafond caractères 10k réel
# Objectif : respecter réellement les options Copilote, générer des blocs
# courts injectables dans le canvas, et plafonner la sortie au max_length UI.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, copywriter conversion senior spécialisé en lead magnets,
pages de capture, offres digitales, MRR, créateurs bloqués et marketing direct francophone.

Priorité absolue : générer des blocs courts qui capturent des emails.
Tu ne rédiges pas une page de vente complète quand l'objectif est de générer des leads.
Tu ne vends pas directement la formation : tu vends l'envie de laisser son email pour obtenir
une micro-transformation rapide, claire et crédible.

Règles obligatoires :
- respecter les options du Copilote ;
- écrire en blocs séparés, faciles à placer dans un canvas ;
- faire court, humain, concret, émotionnel ;
- éviter les pavés, les doublons, les slogans génériques et les promesses irréalistes ;
- utiliser le vocabulaire exact de l'audience et de l'angle demandés ;
- produire uniquement le contenu final, sans explication.
""".strip()


MAX_BRIEF_CHARS = 850
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 120
DEFAULT_OUTPUT_CHARS = 1800
MAX_OUTPUT_CHARS = 10000


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
    return "gpt-4o-mini"


def _clip(value: Optional[str], limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _safe_int(value: Optional[int], default: int = DEFAULT_OUTPUT_CHARS) -> int:
    try:
        n = int(value) if value is not None else default
    except Exception:
        n = default
    return max(400, min(n, MAX_OUTPUT_CHARS))


def _target_output_tokens(char_limit: int) -> int:
    # Approximation prudente : 1 token ≈ 3.5/4 caractères en français.
    # On garde une marge pour éviter les sorties longues côté OpenAI.
    return max(220, min(1800, int(char_limit / 4) + 60))


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
            "TYPE : LEAD MAGNET / CAPTURE EMAIL. But unique : obtenir l'email. "
            "Ne pas vendre directement l'offre principale. Promettre un résultat rapide, gratuit, crédible."
        )
    if page_type == "webinar":
        return "TYPE : WEBINAR. But : inscription à une session avec prise de conscience forte."
    if page_type == "appointment":
        return "TYPE : RDV. But : réserver un diagnostic simple et rassurant."
    if page_type == "bridge":
        return "TYPE : BRIDGE PAGE. But : créer confiance et transition vers l'étape suivante."
    if page_type == "sales":
        return "TYPE : LANDING VENTE. But : désir + confiance + passage à l'achat, sans surpromesse."
    return "TYPE : MODULE COURT. Répondre uniquement au bouton demandé."


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
OPTIONS COPILOTE À RESPECTER :
Objectif : {_clip(objective, 90) or "Générer des leads"}
Type de page : {page_type}
Angle : {_clip(angle, 90) or "conversion claire"}
Audience : {_clip(audience, 120) or "audience froide ou tiède"}
Ton : {_clip(tone, 90) or "humain premium"}
Longueur maximale totale : {max_length} caractères, tous blocs inclus
URL CTA : {_clip(cta_url, 220) or "à renseigner"}
""".strip()


def _goal_instruction(goal: str, page_type: str, max_length: int) -> str:
    value = str(goal or "landing_complete")

    if value == "hooks":
        return "Produit 10 hooks courts. Aucun texte autour."
    if value == "cta":
        return "Produit 10 CTA courts classés doux / direct / émotionnel. Aucun texte autour."
    if value == "benefits":
        return "Produit 8 bénéfices courts : résultat concret + émotion débloquée. Aucun paragraphe."
    if value == "variants":
        return "Produit 3 variantes A/B/C : hook, micro-promesse, CTA. Très court."
    if value == "rewrite_landing":
        return "Réécris le contenu fourni en blocs plus courts. Ne rajoute pas de longueur."

    if page_type == "lead_magnet":
        return (
            "Produit une structure Lead Magnet courte en blocs injectables. "
            "Chaque bloc doit pouvoir devenir un calque texte distinct. "
            "Objectif : capture email maximale, pas vente directe."
        )

    return f"Produit une structure {page_type} courte en blocs injectables. Aucun doublon."


def _format_rules(page_type: str, max_length: int, cta_url: Optional[str]) -> str:
    if page_type == "lead_magnet":
        return f"""
FORMAT EXACT À RESPECTER :
BLOC 1 — HERO
TITRE: 1 phrase courte
SOUS-TITRE: 1 micro-promesse gratuite
CTA: 1 appel à recevoir le guide
URL CTA: {_clip(cta_url, 220) or "à renseigner"}

BLOC 2 — IDENTIFICATION
3 puces maximum, orientées douleur vécue.

BLOC 3 — LEAD MAGNET
3 puces maximum : ce que la personne reçoit gratuitement.

BLOC 4 — POURQUOI ÇA AIDE
2 lignes maximum : mécanisme simple et crédible.

BLOC 5 — RÉASSURANCE
3 puces maximum : pas besoin d'être expert, pas besoin d'audience, pas de promesse magique.

BLOC 6 — CTA FINAL
1 phrase + 1 CTA email.

TOTAL MAXIMUM : {max_length} caractères. Si tu dépasses, supprime la FAQ et raccourcis les puces.
""".strip()

    return f"""
FORMAT EXACT À RESPECTER :
BLOC 1 — HERO
TITRE: 1 phrase courte
SOUS-TITRE: 1 promesse claire
CTA: 1 CTA court
URL CTA: {_clip(cta_url, 220) or "à renseigner"}

BLOC 2 — DOULEUR
3 puces maximum.

BLOC 3 — PROMESSE
3 puces maximum.

BLOC 4 — MÉCANISME
2 lignes maximum.

BLOC 5 — CTA FINAL
1 phrase + 1 CTA.

TOTAL MAXIMUM : {max_length} caractères.
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
) -> tuple[str, int, str]:
    safe_goal = _clip(goal, 80)
    safe_brief = _clip(brief, MAX_BRIEF_CHARS)
    safe_style = _clip(emotional_style, 140) or "humain premium"
    safe_context = _clip(business_context, 200) or "lead generation premium"
    safe_max_length = _safe_int(max_length, DEFAULT_OUTPUT_CHARS)
    inferred_page_type = _infer_page_type(safe_goal, objective, page_type)

    prompt = f"""
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

BRIEF UTILISATEUR :
{safe_brief}

STYLE COMPLÉMENTAIRE : {safe_style}
CONTEXTE MÉTIER : {safe_context}
MÉMOIRE UTILE :
{_memory_block(memories)}

MISSION :
{_goal_instruction(safe_goal, inferred_page_type, safe_max_length)}

CONTRAINTES STRICTES :
- Respecte la longueur maximale totale : {safe_max_length} caractères, titres inclus.
- Réponds uniquement avec les blocs demandés, sans introduction ni commentaire.
- N'écris pas une page de vente si l'objectif est de générer des leads.
- Ne parle pas d'achat direct dans le HERO d'un lead magnet.
- Chaque bloc doit être court et positionnable séparément dans le canvas.
- Utilise l'angle, l'audience et le ton fournis.
- Si l'angle mentionne MRR : parle de formations achetées, dispersion, inaction, première vente.
- Si le ton est storytelling : ajoute une micro-scène concrète, mais très courte.
- Ne répète pas le même bloc sous deux formes.
- Pas de markdown décoratif, pas de tableau, pas de guillemets.

{_format_rules(inferred_page_type, safe_max_length, cta_url)}
""".strip()

    return prompt, safe_max_length, inferred_page_type


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


def _chat_completion(client: Any, *, model: str, messages: list[dict[str, str]], char_limit: int) -> str:
    max_out = _target_output_tokens(char_limit)

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
                temperature=0.45,
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


def _responses_completion(client: Any, *, model: str, prompt: str, char_limit: int) -> str:
    if not hasattr(client, "responses"):
        return ""

    max_out = _target_output_tokens(char_limit)

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


def _trim_to_char_limit(text: str, char_limit: int) -> str:
    cleaned = _dedupe_near_lines(str(text or "").strip())
    if len(cleaned) <= char_limit:
        return cleaned

    cut = cleaned[:char_limit].rstrip()
    break_points = [cut.rfind("\n\nBLOC"), cut.rfind("\nBLOC"), cut.rfind("\n- "), cut.rfind("\n")]
    last_break = max(break_points)
    if last_break > int(char_limit * 0.65):
        cut = cut[:last_break].rstrip()
    return cut.rstrip()


def _compact_output(text: str, *, char_limit: int, page_type: str) -> str:
    hard_limit = _safe_int(char_limit, DEFAULT_OUTPUT_CHARS)
    cleaned = _trim_to_char_limit(text, hard_limit)

    # Sécurité anti-page-de-vente trop longue : si un lead magnet dépasse encore,
    # on retire les blocs secondaires au lieu de renvoyer un pavé.
    if page_type == "lead_magnet" and len(cleaned) > hard_limit:
        parts = cleaned.split("\n\nBLOC")
        cleaned = parts[0]
        for part in parts[1:5]:
            candidate = cleaned + "\n\nBLOC" + part
            if len(candidate) > hard_limit:
                break
            cleaned = candidate

    return cleaned.strip()


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
    prompt, char_limit, inferred_page_type = build_lead_prompt(
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
            content = _chat_completion(client, model=candidate_model, messages=messages, char_limit=char_limit)
            if content:
                return _compact_output(content, char_limit=char_limit, page_type=inferred_page_type)
            content = _responses_completion(client, model=candidate_model, prompt=prompt, char_limit=char_limit)
            if content:
                return _compact_output(content, char_limit=char_limit, page_type=inferred_page_type)
            errors.append(f"{candidate_model}: réponse vide")
        except Exception as exc:
            errors.append(f"{candidate_model}: {exc}")

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
