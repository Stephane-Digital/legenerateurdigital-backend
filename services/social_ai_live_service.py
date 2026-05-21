from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List, Tuple

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class SocialAILiveError(RuntimeError):
    pass


ALLOWED_ROLES = {"hook", "body", "cta", "slide", "title"}

MRR_TOKENS = [
    "mrr",
    "master resale",
    "produit digital",
    "produits digitaux",
    "formation",
    "formations",
    "affiliation",
    "revente",
    "droits de revente",
]

STOP_TOKENS = [
    "arrête",
    "arrete",
    "stop",
    "doit arrêter",
    "doit arreter",
    "arrêter de faire",
    "arreter de faire",
    "commence par ce que",
    "stop doing",
]

FORBIDDEN_WEAK_PHRASES = [
    "vous méritez",
    "tu mérites",
    "croyez en vous",
    "crois en toi",
    "passez à l'action",
    "passe à l'action",
    "connectez-vous avec votre audience",
    "connecte-toi avec ton audience",
    "écoutez votre audience",
    "écoute ton audience",
    "contenu authentique",
    "authenticité",
    "apportez de la valeur",
    "apporte de la valeur",
    "il est essentiel",
    "dans le monde d'aujourd'hui",
    "découvrez comment",
    "optimisez votre stratégie",
    "comprenez ses besoins",
    "comprends ses besoins",
    "résultats concrets",
    "votre potentiel",
    "libérez votre potentiel",
    "libère ton potentiel",
    "transformez votre vie",
    "boostez votre présence",
    "stratégie gagnante",
    "construire une relation de confiance",
    "bâtir des relations authentiques",
    "engage-toi à publier régulièrement",
    "sois constant",
    "reste constant",
    "communauté",
]


# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------

def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").replace("\r", "").strip()
    return text or fallback


def _clip(value: Any, limit: int = 2200) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _model() -> str:
    return (
        os.getenv("OPENAI_MODEL_SOCIAL_AI", "").strip()
        or os.getenv("OPENAI_MODEL_SOCIAL", "").strip()
        or os.getenv("OPENAI_MODEL_TEXT", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise SocialAILiveError("Le package openai n'est pas installé sur le backend.")

    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or "").strip()
    if not api_key:
        raise SocialAILiveError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _all_context(payload: Dict[str, Any]) -> str:
    keys = [
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
    return " ".join(_clean(payload.get(key)) for key in keys).lower()


def _is_mrr(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in MRR_TOKENS)


def _wants_stop(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in STOP_TOKENS)


def _network(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("network"), "Instagram")


def _format(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("format"), "post")


def _goal(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("goal") or payload.get("objective"), "Autorité")


def _category(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("category"), "Conseils")


def _infer_market(payload: Dict[str, Any]) -> str:
    raw = _all_context(payload)
    if any(token in raw for token in MRR_TOKENS):
        return "MRR / produits digitaux"
    if any(token in raw for token in ["coach", "consultant", "accompagnement", "mentor"]):
        return "coaching / service"
    if any(token in raw for token in ["ecommerce", "e-commerce", "shopify", "boutique"]):
        return "e-commerce"
    if any(token in raw for token in ["saas", "logiciel", "application"]):
        return "SaaS"
    return "business digital"


def _extract_json(raw: str) -> Dict[str, Any]:
    text = _clean(raw)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    raise SocialAILiveError("Réponse OpenAI non JSON pour Social AI LIVE.")


def _strip_labels(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(
        r"(?im)^\s*(HOOK|BODY|CTA|TITRE|LÉGENDE|LEGENDE|SLIDE\s*\d*|POST|CAPTION|CONSEIL|ASTUCE)\s*[:：-]\s*",
        "",
        cleaned,
    )
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"\n{4,}", "\n\n", cleaned)
    return cleaned.strip()


def _forbidden_brand_filter(text: str, allowed_offer: str = "") -> str:
    allowed = "lgd" in allowed_offer.lower() or "générateur digital" in allowed_offer.lower() or "generateur digital" in allowed_offer.lower()
    if allowed:
        return text
    cleaned = re.sub(r"\bLe\s+G[eé]n[eé]rateur\s+Digital\b", "ton offre", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bLGD\b", "ton offre", cleaned, flags=re.IGNORECASE)
    return cleaned


def _sanitize_payload_text(data: Dict[str, Any]) -> Dict[str, Any]:
    offer = _clean(data.get("offer") or data.get("product") or data.get("subject") or data.get("prompt"))

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return _forbidden_brand_filter(_strip_labels(value), offer)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    sanitized = walk(data)
    return sanitized if isinstance(sanitized, dict) else data


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ'-]+\b", text or ""))


def _max_words_for(payload: Dict[str, Any]) -> int:
    fmt = _format(payload).lower()
    network = _network(payload).lower()
    if "story" in fmt:
        return 55
    if "reel" in fmt or "tiktok" in network:
        return 115
    if "linkedin" in network or "linkedin" in fmt:
        return 145
    if "carrousel" in fmt:
        return 38
    return 118


def _mobile_linebreak(text: str) -> str:
    raw = _strip_labels(text)
    raw = re.sub(r"[ \t]+", " ", raw)
    source_lines = [line.strip() for line in raw.split("\n")]
    out: List[str] = []

    for line in source_lines:
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue

        # Keep bullet/list lines.
        if re.match(r"^[-•]\s+", line):
            out.append(line)
            continue

        words = line.split()
        if len(words) <= 8:
            out.append(line)
            continue

        # First split by sentence, then by chunks.
        sentences = re.split(r"(?<=[.!?…])\s+", line)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            s_words = sentence.split()
            if len(s_words) <= 8:
                out.append(sentence)
            else:
                for i in range(0, len(s_words), 7):
                    out.append(" ".join(s_words[i : i + 7]).strip())

    # Collapse repeated blanks, but keep breathing between lines.
    cleaned: List[str] = []
    previous_blank = False
    for line in out:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = blank

    return "\n\n".join(line for line in cleaned if line.strip()).strip()


def _trim_words(text: str, max_words: int) -> str:
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).strip()
    clipped = re.sub(r"[,;:]$", "", clipped).strip()
    return clipped + "."


def _has_long_paragraph(text: str) -> bool:
    for paragraph in re.split(r"\n\s*\n", text or ""):
        if _word_count(paragraph) > 22:
            return True
    return False


def _looks_weak(text: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    lower = text.lower()
    for phrase in FORBIDDEN_WEAK_PHRASES:
        if phrase in lower:
            return True, f"phrase interdite: {phrase}"
    if _word_count(text) > _max_words_for(payload) + 12:
        return True, "trop long"
    if _has_long_paragraph(text):
        return True, "pavé détecté"
    if _is_mrr(payload) and not any(token in lower for token in ["mrr", "formation", "formations", "vidéo", "video", "publie", "publier", "contenu", "prospect", "vente", "vendre"]):
        return True, "MRR pas assez incarné"
    if _wants_stop(payload) and not any(token in lower for token in ["arrête", "arrete", "stop"]):
        return True, "arrête de non respecté"
    return False, "ok"


def _normalize_string_list(value: Any, limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        text = _clean(item)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _flat_text(blocks: List[Dict[str, str]]) -> str:
    return "\n\n".join(_clean(block.get("text")) for block in blocks if _clean(block.get("text")))


def _normalize_blocks(value: Any, payload: Dict[str, Any]) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

    max_words = _max_words_for(payload)
    blocks: List[Dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role"), "body").lower()
        if role not in ALLOWED_ROLES:
            role = "body"
        text = _strip_labels(_clean(item.get("text")))
        if not text:
            continue

        if role in {"hook", "body", "cta"}:
            limit = max_words
            if role == "hook":
                limit = 26
            elif role == "cta":
                limit = 24
            text = _trim_words(text, limit)
            text = _mobile_linebreak(text)
        elif role == "slide":
            text = _trim_words(text, 34)
            text = _mobile_linebreak(text)

        blocks.append({"role": role, "text": text})

    if not blocks:
        raise SocialAILiveError("Réponse Social AI LIVE vide.")

    return blocks[:12]


# -----------------------------------------------------------------------------
# Prompting LIVE — no static fallback
# -----------------------------------------------------------------------------

def _system_prompt() -> str:
    return """
Tu es SOCIAL AI LIVE — copywriter terrain pour entrepreneurs du digital.

Tu n'es PAS un coach motivationnel.
Tu n'es PAS un prof marketing.
Tu n'es PAS LinkedIn corporate.
Tu n'écris jamais de pavés.

MISSION
Écrire un contenu social prêt à publier, court, mobile-first, spécifique et incarné.
Le lecteur doit penser : « putain, c'est moi ».

RÈGLES NON NÉGOCIABLES
- une seule idée forte par génération ;
- phrases courtes ;
- beaucoup de respiration ;
- zéro paragraphe compact ;
- zéro théorie ;
- zéro conseil vague ;
- zéro motivation bullshit ;
- zéro formule corporate ;
- zéro mention LGD / Le Générateur Digital sauf si l'utilisateur le demande explicitement ;
- obéir au brief, pas l'interpréter librement.

INTERDITS ABSOLUS
"vous méritez", "croyez en vous", "passez à l'action", "contenu authentique", "écoutez votre audience", "apportez de la valeur", "optimisez votre stratégie", "il est essentiel", "découvrez comment", "boostez votre présence", "construire une relation", "communauté", "sois constant".

SI LE CONTEXTE EST MRR / PRODUITS DIGITAUX
Tu dois parler terrain :
formations achetées, vidéos TikTok, stratégies sauvegardées, page blanche, publication, contenu posté, prospects, ventes, exécution.

SI LE BRIEF DEMANDE DE COMMENCER PAR CE QUE L'AUDIENCE DOIT ARRÊTER DE FAIRE
Tu dois commencer par :
"Si tu débutes dans le MRR :"

puis :
"arrête de ..."

STYLE VÉRITÉ À IMITER
Si tu débutes dans le MRR :

arrête de regarder des vidéos toute la journée.

Oui.

Vraiment.

Parce qu'à un moment :

tu n'as plus un problème d'information.

Tu as un problème d'exécution.

Tu regardes :

une vidéo TikTok
une autre stratégie
une autre méthode

Et le soir ?

Toujours zéro contenu publié.

Zéro prospect.

Zéro vente.

Le vrai déclic :

publier imparfaitement.

Parce qu'un contenu imparfait posté aujourd'hui…

bat toujours une stratégie “parfaite” restée dans ta tête.

SORTIE
Réponds uniquement en JSON valide.
Aucun markdown.
Aucun texte hors JSON.
""".strip()


def _context_prompt(payload: Dict[str, Any]) -> str:
    return f"""
CONTEXTE À RESPECTER STRICTEMENT
Format : {_format(payload)}
Réseau : {_network(payload)}
Objectif : {_goal(payload)}
Catégorie / angle : {_category(payload)}
Ton : {_clean(payload.get('tone'), 'direct, premium, humain, anti-blabla')}
Marché inféré : {_infer_market(payload)}
Offre / sujet : {_clip(payload.get('offer') or payload.get('product') or payload.get('subject') or payload.get('prompt'), 900)}
Audience : {_clip(payload.get('audience') or payload.get('target'), 900)}
Douleur : {_clip(payload.get('pain'), 700)}
Promesse / résultat : {_clip(payload.get('promise') or payload.get('result'), 700)}
Objection : {_clip(payload.get('objection'), 500)}
CTA souhaité : {_clip(payload.get('cta'), 500)}
Brief libre exact : {_clip(payload.get('prompt') or payload.get('brief') or payload.get('context'), 1800)}
""".strip()


def _quality_prompt(payload: Dict[str, Any]) -> str:
    market = _infer_market(payload)
    fmt = _format(payload).lower()
    network = _network(payload).lower()
    category = _category(payload).lower()
    goal = _goal(payload).lower()

    if "story" in fmt:
        max_line = "35 à 55 mots maximum."
    elif "reel" in fmt or "tiktok" in network:
        max_line = "90 à 115 mots maximum."
    elif "linkedin" in fmt or "linkedin" in network:
        max_line = "120 à 145 mots maximum, respirant, jamais article."
    elif "carrousel" in fmt:
        max_line = "Chaque slide : 12 à 28 mots maximum."
    else:
        max_line = "80 à 118 mots maximum."

    category_rule = "Donne une vérité utile et spécifique."
    if "mrr" in category or "mrr" in market.lower():
        category_rule = "Parle au débutant MRR qui consomme trop, publie peu, doute, veut vendre mais n'exécute pas."
    elif "algorith" in category:
        category_rule = "Donne un conseil algorithme simple et applicable : hook, rétention, sauvegarde, commentaire, timing ou recyclage."
    elif "viral" in category:
        category_rule = "Écris une vérité partageable, relatable, sans buzz vide."
    elif "conversion" in category or "convert" in goal or "vente" in category:
        category_rule = "Crée une prise de conscience qui rapproche d'une décision sans argumentaire lourd."
    elif "conseil" in category:
        category_rule = "Une seule idée utile que l'audience peut appliquer aujourd'hui."

    start_rule = ""
    if _wants_stop(payload) and _is_mrr(payload):
        start_rule = """
DÉBUT OBLIGATOIRE
Le hook doit commencer par :
Si tu débutes dans le MRR :

La ligne suivante doit commencer par :
arrête de ...

Ne parle pas des gourous.
Ne parle pas de contenu authentique.
Ne parle pas de communauté.
""".strip()
    elif _wants_stop(payload):
        start_rule = """
DÉBUT OBLIGATOIRE
Le hook ou la première ligne doit commencer par :
arrête de ...
""".strip()

    return f"""
CADRE QUALITÉ
{max_line}
{category_rule}
{start_rule}

STRUCTURE POUR POST SIMPLE
1. Situation spécifique.
2. Vérité qui pique.
3. Exemple terrain.
4. Déclic.
5. Phrase mémorable.
6. CTA court seulement si utile.

NE PAS ÉCRIRE
- un article ;
- un résumé marketing ;
- une leçon générale ;
- un conseil bateau ;
- un post motivation.
""".strip()


def _single_generation_prompt(payload: Dict[str, Any]) -> str:
    seed = random.randint(10000, 999999)
    fmt = _format(payload).lower()

    if "carrousel" in fmt:
        blocks_rule = "Retourne 6 blocks role='slide' + 1 block role='cta'. Une seule idée par slide."
    elif "reel" in fmt:
        blocks_rule = "Retourne 1 block role='hook', 1 block role='body' en script vidéo court, 1 block role='cta'."
    else:
        blocks_rule = "Retourne exactement 3 blocks : hook, body, cta. Aucun texte long."

    return f"""
{_context_prompt(payload)}

{_quality_prompt(payload)}

VARIATION LIVE
Seed : {seed}
Génère un angle vivant et spécifique, pas un template.

{blocks_rule}

JSON STRICT
{{
  "title": "titre interne court",
  "blocks": [
    {{"role": "hook", "text": "..."}},
    {{"role": "body", "text": "..."}},
    {{"role": "cta", "text": "..."}}
  ],
  "performance": {{
    "recommended_format": "...",
    "publish_tip": "...",
    "algorithm_tip": "...",
    "visual_idea": "...",
    "variation_idea": "..."
  }},
  "angles": ["...", "...", "..."]
}}
""".strip()


def _repair_prompt(payload: Dict[str, Any], bad_text: str, reason: str) -> str:
    return f"""
Le contenu précédent est REFUSÉ.
Raison : {reason}

Contenu refusé :
{_clip(bad_text, 1500)}

Réécris entièrement.

{_context_prompt(payload)}

{_quality_prompt(payload)}

RÈGLES DE CORRECTION
- Pas de pavé.
- Pas de phrase corporate.
- Pas de motivation creuse.
- Pas de conseil vague.
- Si MRR : parle d'exécution, vidéos, formations, publication, prospects, ventes.
- Si le brief demande "arrête de" : commence par "arrête de".
- Fais respirer chaque ligne.

JSON strict avec blocks hook/body/cta.
""".strip()


def _plan_90_prompt(payload: Dict[str, Any]) -> str:
    return f"""
{_context_prompt(payload)}

MISSION LIVE IA : PLAN 90 JOURS
Crée un calendrier de 90 jours pour aider l'utilisateur à conseiller son audience.
Ne génère pas 90 posts complets.
Génère 90 angles courts, utiles, variés, non répétitifs.

Chaque jour :
- day
- theme
- angle
- objective
- recommended_format
- hook_seed
- audience_benefit
- algorithm_tip
- cta_type

RÈGLES
- 90 jours exactement.
- Aucun angle générique.
- Aucun doublon.
- Mobile-first.
- Spécifique à la niche.
- Pas de LGD.

JSON STRICT
{{
  "title": "Plan 90 jours - ...",
  "days": [
    {{
      "day": 1,
      "theme": "...",
      "angle": "...",
      "objective": "...",
      "recommended_format": "...",
      "hook_seed": "...",
      "audience_benefit": "...",
      "algorithm_tip": "...",
      "cta_type": "..."
    }}
  ]
}}
""".strip()


def _openai_json(prompt: str, *, max_tokens: int, temperature: float) -> Dict[str, Any]:
    client = _get_client()
    response = client.chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        top_p=0.86,
        frequency_penalty=1.05,
        presence_penalty=0.8,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    if not raw.strip():
        raise SocialAILiveError("Réponse OpenAI vide pour Social AI LIVE.")
    return _extract_json(raw)


# -----------------------------------------------------------------------------
# Public API service functions
# -----------------------------------------------------------------------------

def estimate_tokens(*parts: Any) -> int:
    text = " ".join(str(part or "") for part in parts)
    return max(1, int(len(text) / 4))


def generate_social_ai_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))

    data = _openai_json(
        _single_generation_prompt(safe_payload),
        max_tokens=900,
        temperature=0.86 + random.random() * 0.08,
    )
    data = _sanitize_payload_text(data)
    blocks = _normalize_blocks(data.get("blocks"), safe_payload)

    full_text = _flat_text(blocks)
    weak, reason = _looks_weak(full_text, safe_payload)
    attempts = 0
    while weak and attempts < 3:
        attempts += 1
        data = _openai_json(
            _repair_prompt(safe_payload, full_text, reason),
            max_tokens=780,
            temperature=0.92 + random.random() * 0.05,
        )
        data = _sanitize_payload_text(data)
        blocks = _normalize_blocks(data.get("blocks"), safe_payload)
        full_text = _flat_text(blocks)
        weak, reason = _looks_weak(full_text, safe_payload)

    if weak:
        raise SocialAILiveError(f"Qualité Social AI refusée après 3 corrections LIVE : {reason}")

    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}
    return {
        "ok": True,
        "mode": "live_ai_truth_reset_no_fallback",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post mobile-first court."),
            "publish_tip": _clean(performance.get("publish_tip"), "Publie quand ton audience peut répondre, puis mesure les commentaires qualifiés."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "La première ligne doit faire comprendre en 3 secondes pourquoi le lecteur est concerné."),
            "visual_idea": _clean(performance.get("visual_idea"), "Une phrase forte en grand, peu de texte, contraste lisible."),
            "variation_idea": _clean(performance.get("variation_idea"), "Teste le même angle avec une douleur ou objection différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    data = _openai_json(_plan_90_prompt(safe_payload), max_tokens=6500, temperature=0.78)
    data = _sanitize_payload_text(data)

    raw_days = data.get("days")
    if not isinstance(raw_days, list):
        raise SocialAILiveError("Plan 90 jours invalide : days manquant.")

    days: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_days[:90], start=1):
        if not isinstance(item, dict):
            continue
        days.append(
            {
                "day": int(item.get("day") or index),
                "theme": _clean(item.get("theme"), f"Conseil jour {index}"),
                "angle": _clean(item.get("angle"), "Conseil utile"),
                "objective": _clean(item.get("objective"), "Créer de l'autorité"),
                "recommended_format": _clean(item.get("recommended_format"), "Post simple"),
                "hook_seed": _clean(item.get("hook_seed"), "Une vérité utile que ton audience doit entendre."),
                "audience_benefit": _clean(item.get("audience_benefit"), "Comprendre quoi faire ensuite."),
                "algorithm_tip": _clean(item.get("algorithm_tip"), "Commence par une tension claire."),
                "cta_type": _clean(item.get("cta_type"), "Question commentaire"),
            }
        )

    if len(days) < 90:
        raise SocialAILiveError("Le plan Social AI LIVE n'a pas généré 90 jours complets.")

    return {
        "ok": True,
        "mode": "live_ai_90_day_plan_truth_reset",
        "title": _clean(data.get("title"), "Plan 90 jours de conseils"),
        "days": days,
    }


def generate_social_ai_day_from_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    day_data = payload.get("day_data") if isinstance(payload.get("day_data"), dict) else {}
    merged = dict(payload or {})
    merged["category"] = _clean(merged.get("category"), "Conseils")
    merged["prompt"] = "\n".join(
        [
            _clean(merged.get("prompt") or merged.get("brief")),
            f"Jour : {_clean(day_data.get('day'))}",
            f"Thème : {_clean(day_data.get('theme'))}",
            f"Angle : {_clean(day_data.get('angle'))}",
            f"Objectif : {_clean(day_data.get('objective'))}",
            f"Hook seed : {_clean(day_data.get('hook_seed'))}",
            f"Bénéfice audience : {_clean(day_data.get('audience_benefit'))}",
            f"Conseil algorithme : {_clean(day_data.get('algorithm_tip'))}",
            f"CTA : {_clean(day_data.get('cta_type'))}",
            "Génère le post complet de ce jour. Court, spécifique, mobile-first, zéro pavé.",
        ]
    ).strip()
    return generate_social_ai_live(merged)
