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


ALLOWED_ROLES = {"hook", "body", "cta", "slide", "title"}

FORBIDDEN_WEAK_PHRASES = [
    "vous méritez",
    "croyez en vous",
    "crois en toi",
    "passez à l'action",
    "passe à l'action",
    "connectez-vous avec votre audience",
    "connecte-toi avec ton audience",
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
    "libere ton potentiel",
    "transformez votre vie",
    "boostez votre présence",
    "stratégie gagnante",
    "identifiez une niche",
    "créez du contenu de qualité",
    "crée du contenu de qualité",
    "soyez régulier",
]

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


TRUTH_STYLE = """
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
""".strip()


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


def _infer_market(payload: Dict[str, Any]) -> str:
    raw = _all_context(payload)
    if any(token in raw for token in MRR_TOKENS):
        return "MRR / produits digitaux"
    if any(token in raw for token in ["coach", "consultant", "accompagnement", "mentor"]):
        return "coaching / service"
    if any(token in raw for token in ["ecommerce", "e-commerce", "boutique", "shopify"]):
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
    fmt = _clean(payload.get("format"), "post").lower()
    network = _clean(payload.get("network"), "Instagram").lower()
    if "story" in fmt:
        return 55
    if "reel" in fmt or "tiktok" in network:
        return 105
    if "linkedin" in network or "linkedin" in fmt:
        return 145
    if "carrousel" in fmt:
        return 36
    return 125


def _has_long_paragraph(text: str) -> bool:
    for paragraph in re.split(r"\n\s*\n", text or ""):
        if _word_count(paragraph) > 24:
            return True
    return False


def _split_mobile_lines(text: str) -> str:
    raw = _strip_labels(text)
    if not raw:
        return raw

    out: List[str] = []
    for original_line in raw.split("\n"):
        line = original_line.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue

        if len(line.split()) <= 8:
            out.append(line)
            continue

        parts = re.split(r"(?<=[.!?…:])\s+", line)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            words = part.split()
            if len(words) <= 8:
                out.append(part)
            else:
                for i in range(0, len(words), 7):
                    out.append(" ".join(words[i : i + 7]).strip())

    compacted: List[str] = []
    previous_blank = False
    for line in out:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compacted.append(line)
        previous_blank = blank

    # Une ligne = une respiration. On force double saut pour le rendu mobile dans le canvas.
    return "\n\n".join(line for line in compacted if line.strip())


def _trim_to_mobile(text: str, payload: Dict[str, Any]) -> str:
    max_words = _max_words_for(payload)
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).strip()
    clipped = re.sub(r"[,;:]?$", "", clipped).strip()
    return clipped + "."


def _normalize_blocks(value: Any, payload: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

    blocks: List[Dict[str, str]] = []
    payload = payload or {}
    for item in value:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role"), "body").lower()
        text = _strip_labels(_clean(item.get("text")))
        if role not in ALLOWED_ROLES:
            role = "body"
        if text:
            if role in {"body", "hook", "cta"}:
                text = _trim_to_mobile(text, payload)
                text = _split_mobile_lines(text)
            blocks.append({"role": role, "text": text})

    if not blocks:
        raise SocialAILiveError("Réponse Social AI LIVE vide.")

    return blocks[:12]


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


def _flat_text_from_blocks(blocks: List[Dict[str, str]]) -> str:
    return "\n\n".join(_clean(block.get("text")) for block in blocks if _clean(block.get("text")))


def _looks_weak(text: str, payload: Dict[str, Any] | None = None) -> bool:
    payload = payload or {}
    lower = text.lower()
    if any(phrase in lower for phrase in FORBIDDEN_WEAK_PHRASES):
        return True
    if _word_count(text) > _max_words_for(payload) + 18:
        return True
    if _has_long_paragraph(text):
        return True
    if _is_mrr(payload) and not any(token in lower for token in ["mrr", "formation", "formations", "publier", "contenu", "vente", "prospect", "vidéo", "video", "tiktok", "stratégie", "strategie"]):
        return True
    if _wants_stop_doing(payload) and not any(token in lower for token in ["arrête", "arrete", "stop"]):
        return True
    # Rejet des conseils trop vagues.
    if "niche" in lower and "mrr" in _all_context(payload) and not any(token in lower for token in ["contenu", "publier", "formation", "vente", "prospect"]):
        return True
    return False


def _context_prompt(payload: Dict[str, Any]) -> str:
    return f"""
CONTEXTE UTILISATEUR À RESPECTER À 100 %
- Format demandé : {_clean(payload.get('format'), 'post')}
- Réseau : {_clean(payload.get('network'), 'Instagram')}
- Objectif : {_clean(payload.get('goal') or payload.get('objective'), 'Autorité')}
- Catégorie / angle : {_clean(payload.get('category'), 'Conseils')}
- Ton demandé : {_clean(payload.get('tone'), 'direct, humain, premium')}
- Marché inféré : {_infer_market(payload)}
- Offre / produit / sujet : {_clip(payload.get('offer') or payload.get('product') or payload.get('subject') or payload.get('prompt'), 1000)}
- Audience : {_clip(payload.get('audience') or payload.get('target'), 1000)}
- Douleur : {_clip(payload.get('pain'), 800)}
- Promesse / résultat : {_clip(payload.get('promise') or payload.get('result'), 800)}
- Objection : {_clip(payload.get('objection'), 600)}
- CTA souhaité : {_clip(payload.get('cta'), 500)}
- Brief libre : {_clip(payload.get('prompt') or payload.get('brief') or payload.get('context'), 2000)}

OBÉISSANCE STRICTE
- Tu ne remplaces jamais la demande par un conseil général.
- Si le brief dit "commence par", tu commences par cette intention.
- Si le brief dit "arrête de", tu écris une première idée en "arrête de ...".
- Si le brief contient MRR / formation / produit digital, tu parles de publication, exécution, contenu, prospects, ventes, vidéos, formations ou stratégies achetées.
""".strip()


def _system_prompt() -> str:
    return f"""
Tu es SOCIAL AI RESET TRUTH.
Tu écris pour des créateurs business, MRR, produits digitaux, coachs, indépendants et e-commerce.
Tu ne fais PAS de conseils corporate.
Tu ne fais PAS de mini-article.
Tu ne fais PAS de motivation creuse.
Tu écris comme quelqu'un qui connaît vraiment le terrain.

RÈGLE ABSOLUE : ZÉRO PAVÉ
- jamais de paragraphe compact ;
- jamais de cours marketing ;
- jamais de dissertation ;
- jamais "voici pourquoi" en mode article ;
- 1 idée forte = 1 post.

STYLE OBLIGATOIRE
- mobile-first ;
- phrases courtes ;
- beaucoup de respiration ;
- vérité qui pique ;
- situation concrète ;
- douleur réelle ;
- exemple terrain ;
- chute mémorable ;
- publiable immédiatement.

INTERDITS ABSOLUS
- vous méritez ;
- croyez en vous ;
- passez à l'action ;
- écoutez votre audience ;
- contenu authentique ;
- apportez de la valeur ;
- optimisez votre stratégie ;
- stratégie gagnante ;
- boostez votre présence ;
- créez du contenu de qualité ;
- identifiez une niche ;
- dans le monde d'aujourd'hui ;
- il est essentiel.

SI MRR / PRODUITS DIGITAUX
Tu dois utiliser le terrain réel :
formations achetées, vidéos TikTok, stratégies, page blanche, contenu publié, prospects, ventes, exécution, peur de poster, consommation passive.
Tu ne dois PAS parler de gourous, niche ou authenticité sauf si l'utilisateur le demande.

SI "ARRÊTE DE" EST DEMANDÉ
Tu commences par un angle proche de :
"Si tu débutes dans [niche] :"

Puis :
"arrête de ..."

RÉFÉRENCE VÉRITÉ À IMITER EN STYLE, RYTHME ET DENSITÉ
{TRUTH_STYLE}

SORTIE TECHNIQUE
Réponds uniquement en JSON valide.
Aucun markdown.
Aucun texte hors JSON.
""".strip()


def _quality_frame(payload: Dict[str, Any]) -> str:
    category = _clean(payload.get("category"), "Conseils").lower()
    network = _clean(payload.get("network"), "Instagram").lower()
    fmt = _clean(payload.get("format"), "post").lower()
    goal = _clean(payload.get("goal") or payload.get("objective"), "Autorité").lower()
    market = _infer_market(payload)

    category_line = "Donne un conseil utile, précis, sauvegardable. Une seule idée."
    if "algorith" in category:
        category_line = "Explique un principe d'algorithme en une action terrain simple : hook, rétention, sauvegarde, commentaire, timing ou recyclage."
    elif "viral" in category:
        category_line = "Crée une vérité relatable et partageable. Pas de buzz vide."
    elif "conversion" in category or "vente" in category or "convert" in goal:
        category_line = "Crée une prise de conscience qui rapproche de la décision sans vendre lourdement."
    elif "mrr" in category or "MRR" in market:
        category_line = "Parle au débutant MRR qui consomme, hésite, publie peu, veut vendre mais reste bloqué."

    if "tiktok" in network or "reel" in fmt:
        format_line = "Vidéo courte : 1 phrase par ligne, hook immédiat, aucun paragraphe."
        max_words = "90 à 110 mots maximum."
    elif "linkedin" in network:
        format_line = "LinkedIn : point de vue net, respirant. Jamais article."
        max_words = "120 à 145 mots maximum."
    elif "story" in fmt:
        format_line = "Story : ultra court, impact immédiat, très peu de texte."
        max_words = "25 à 55 mots maximum."
    else:
        format_line = "Instagram/Facebook : mobile-first, lignes courtes, respiration, punchline utile."
        max_words = "80 à 125 mots maximum."

    strict_start = ""
    if _wants_stop_doing(payload) and _is_mrr(payload):
        strict_start = """
DÉBUT OBLIGATOIRE
La première ligne doit être proche de :
"Si tu débutes dans le MRR :"

La deuxième idée doit commencer par :
"arrête de ..."

Ne parle pas de gourous.
Ne parle pas de niche.
Ne parle pas d'authenticité.
Ne parle pas de confiance en général.
""".strip()
    elif _wants_stop_doing(payload):
        strict_start = """
DÉBUT OBLIGATOIRE
La première idée doit commencer par "arrête de ...".
Ne transforme pas ça en conseil général.
""".strip()

    return f"""
CADRE QUALITÉ
- Marché : {market}
- Angle prioritaire : {category_line}
- Format : {format_line}
- Longueur : {max_words}
{strict_start}

STRUCTURE POST SIMPLE
1. Situation spécifique.
2. Vérité qui pique.
3. Exemple terrain.
4. Déclic.
5. Phrase mémorable.
6. CTA uniquement si utile.

OBLIGATION DE STYLE
- pas de long paragraphe ;
- pas de conseil vague ;
- pas de phrase corporate ;
- pas de morale ;
- pas de "il faut" répété ;
- pas de liste interminable ;
- chaque ligne doit être lisible sur mobile.
""".strip()


def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    fmt = _clean(payload.get("format"), "post").lower()
    seed = random.randint(10000, 999999)

    if fmt == "carrousel":
        blocks_rule = "Retourne 6 blocks role='slide' + 1 block role='cta'. Chaque slide = 16 mots max."
    elif fmt == "reel":
        blocks_rule = "Retourne 1 block role='hook', 1 block role='body' en script vidéo respirant, 1 block role='cta'."
    else:
        blocks_rule = "Retourne exactement 3 blocks : role='hook', role='body', role='cta'. Le body doit être court, aéré, mobile-first."

    return f"""
{_context_prompt(payload)}

{_quality_frame(payload)}

VARIATION LIVE
Seed créatif : {seed}
Tu dois produire un angle réel, pas une reformulation générique.

CONTRAINTE PRINCIPALE
Écris comme si l'utilisateur allait poster dans Instagram maintenant.
Le texte doit donner l'impression : "putain, il parle de moi".

{blocks_rule}

FORMAT JSON STRICT
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


def _repair_user_prompt(payload: Dict[str, Any], bad_text: str) -> str:
    return f"""
Le contenu suivant est REFUSÉ :
{_clip(bad_text, 1400)}

Raison : trop générique, trop lourd, hors sujet ou pas assez mobile-first.

{_context_prompt(payload)}

{_quality_frame(payload)}

Réécris entièrement.
Tu dois te rapprocher du rythme de cette référence :
{TRUTH_STYLE}

JSON STRICT avec blocks hook/body/cta.
""".strip()


def _plan_90_user_prompt(payload: Dict[str, Any]) -> str:
    return f"""
{_context_prompt(payload)}

MISSION : PLAN 90 JOURS DE CONSEILS EXPERTS
Crée un calendrier de 90 jours pour aider l'utilisateur à conseiller son audience.
Ne génère PAS 90 posts complets.
Génère 90 angles courts, variés, actionnables, non répétitifs.

CHAQUE JOUR DOIT CONTENIR
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
- Zéro pavé.
- Alternance : conseil, erreur, algorithme, viralité douce, objection, conversion, storytelling, lead magnet, régularité, recyclage, CTA, preuve, confiance, anti-page blanche.
- hook_seed = court, spécifique, publiable.
- Jamais LGD.

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


def _generate_json(prompt: str, *, max_tokens: int, temperature: float) -> Dict[str, Any]:
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


def estimate_tokens(*parts: Any) -> int:
    text = " ".join(str(p or "") for p in parts)
    return max(1, int(len(text) / 4))


def _postprocess_blocks(blocks: List[Dict[str, str]], payload: Dict[str, Any]) -> List[Dict[str, str]]:
    processed: List[Dict[str, str]] = []
    for block in blocks:
        role = _clean(block.get("role"), "body").lower()
        text = _clean(block.get("text"))
        if role in {"hook", "body", "cta"}:
            text = _trim_to_mobile(text, payload)
            text = _split_mobile_lines(text)
        processed.append({"role": role if role in ALLOWED_ROLES else "body", "text": text})
    return processed


def generate_social_ai_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _single_generation_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=950, temperature=0.84 + random.random() * 0.08)
    data = _sanitize_payload_text(data)
    blocks = _normalize_blocks(data.get("blocks"), safe_payload)
    blocks = _postprocess_blocks(blocks, safe_payload)

    full_text = _flat_text_from_blocks(blocks)
    repair_attempts = 0
    while _looks_weak(full_text, safe_payload) and repair_attempts < 3:
        repair_attempts += 1
        repair_prompt = _repair_user_prompt(safe_payload, full_text)
        data = _generate_json(repair_prompt, max_tokens=900, temperature=0.9 + random.random() * 0.06)
        data = _sanitize_payload_text(data)
        blocks = _normalize_blocks(data.get("blocks"), safe_payload)
        blocks = _postprocess_blocks(blocks, safe_payload)
        full_text = _flat_text_from_blocks(blocks)

    if _looks_weak(full_text, safe_payload):
        raise SocialAILiveError("Social AI LIVE a refusé de livrer un contenu faible après régénération.")

    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai_reset_truth_zero_pave_verified",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post court mobile-first ou Reel selon le réseau."),
            "publish_tip": _clean(performance.get("publish_tip"), "Publie quand ton audience peut lire calmement, puis mesure les réponses qualifiées."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "La première ligne doit faire comprendre en 3 secondes pourquoi le lecteur est concerné."),
            "visual_idea": _clean(performance.get("visual_idea"), "Une phrase forte en grand, peu de texte, contraste lisible."),
            "variation_idea": _clean(performance.get("variation_idea"), "Réécris le même angle avec une situation terrain différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _plan_90_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=6500, temperature=0.78)
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
        "mode": "live_ai_90_day_plan_reset_truth",
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
            "Génère maintenant le post complet de ce jour. Fais court, spécifique, mobile-first, non générique, zéro pavé.",
        ]
    ).strip()
    return generate_social_ai_live(merged)
