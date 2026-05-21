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
    "passez à l'action",
    "connectez-vous avec votre audience",
    "écoutez votre audience",
    "ecoutez votre audience",
    "contenu authentique",
    "apportez de la valeur",
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
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
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
    if isinstance(sanitized, dict):
        return sanitized
    return data


def _normalize_blocks(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

    blocks: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role"), "body").lower()
        text = _strip_labels(_clean(item.get("text")))
        if role not in ALLOWED_ROLES:
            role = "body"
        if text:
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


def _looks_weak(text: str) -> bool:
    lower = text.lower()
    if any(phrase in lower for phrase in FORBIDDEN_WEAK_PHRASES):
        return True
    if len(text.split()) > 230:
        return True
    if "marketing digital" in lower and "mrr" not in lower and "formation" not in lower and "offre" not in lower:
        # Le texte reste trop générique si le sujet demandé est large.
        return True
    return False


def _infer_market(payload: Dict[str, Any]) -> str:
    raw = " ".join(
        _clean(payload.get(key))
        for key in ["prompt", "brief", "context", "offer", "product", "subject", "audience", "target", "category"]
    ).lower()
    if any(token in raw for token in ["mrr", "master resale", "revente", "produit digital", "produits digitaux", "affiliation"]):
        return "MRR / produits digitaux"
    if any(token in raw for token in ["coach", "consultant", "accompagnement", "mentor"]):
        return "coaching / service"
    if any(token in raw for token in ["ecommerce", "e-commerce", "boutique", "shopify"]):
        return "e-commerce"
    if any(token in raw for token in ["saas", "logiciel", "application"]):
        return "SaaS"
    return "business digital"


def _context_prompt(payload: Dict[str, Any]) -> str:
    return f"""
CONTEXTE UTILISATEUR À RESPECTER
- Format demandé : {_clean(payload.get('format'), 'post')}
- Réseau : {_clean(payload.get('network'), 'Instagram')}
- Objectif : {_clean(payload.get('goal') or payload.get('objective'), 'Autorité')}
- Catégorie / angle : {_clean(payload.get('category'), 'Conseils')}
- Ton demandé : {_clean(payload.get('tone'), 'direct, humain, premium')}
- Marché inféré : {_infer_market(payload)}
- Offre / produit / sujet : {_clip(payload.get('offer') or payload.get('product') or payload.get('subject') or payload.get('prompt'), 1100)}
- Audience : {_clip(payload.get('audience') or payload.get('target'), 1100)}
- Douleur : {_clip(payload.get('pain'), 900)}
- Promesse / résultat : {_clip(payload.get('promise') or payload.get('result'), 900)}
- Objection : {_clip(payload.get('objection'), 700)}
- CTA souhaité : {_clip(payload.get('cta'), 500)}
- Brief libre : {_clip(payload.get('prompt') or payload.get('brief') or payload.get('context'), 2200)}

SI LE BRIEF EST FLOU
Tu dois choisir une situation concrète, pas écrire général.
Exemples de situations concrètes possibles :
- l'audience consomme plus de contenu qu'elle n'en publie ;
- elle achète des formations mais ne passe pas à l'action ;
- elle veut vendre mais n'ose pas publier ;
- elle change de stratégie tous les trois jours ;
- elle confond apprendre et avancer ;
- elle veut être crédible mais parle trop vaguement ;
- elle a une offre mais aucune confiance réelle de son audience.
""".strip()


def _system_prompt() -> str:
    return """
Tu es SOCIAL AI V4 FINAL — cerveau LIVE premium pour créer des contenus sociaux que l'utilisateur peut publier directement.

RÈGLE MARQUE ABSOLUE
Tu ne mentionnes jamais LGD, Le Générateur Digital, une plateforme interne, un outil ou une marque non explicitement fournie par l'utilisateur.
L'utilisateur doit apparaître comme la personne intéressante à suivre dans SA niche.

TA MISSION
Créer un contenu court, lisible, humain, spécifique, mobile-first, qui donne envie de dire : « putain, c'est vrai ».
Tu ne donnes pas un cours marketing. Tu écris un vrai post social.
Le contenu doit aider l'utilisateur à conseiller son audience, créer autorité, confiance, commentaires, leads ou ventes.

CE QUE TU DOIS ABSOLUMENT ÉVITER
Interdits :
- « vous méritez », « croyez en vous », « passez à l'action » ;
- « contenu authentique », « écoutez votre audience », « comprenez ses besoins » ;
- « il est essentiel », « dans le monde d'aujourd'hui », « découvrez comment » ;
- phrases motivationnelles vagues ;
- article mini-blog ;
- paragraphes longs ;
- ton LinkedIn corporate ;
- blabla marketing abstrait ;
- labels HOOK / BODY / CTA dans le texte final.

MÉTHODE INVISIBLE OBLIGATOIRE
Avant d'écrire, tu dois raisonner mentalement en 5 étapes :
1. Identifier le vrai humain derrière le brief : débutant MRR, coach, e-commerçant, créateur, indépendant, etc.
2. Identifier le comportement qui bloque : consommer sans publier, vouloir tout optimiser, attendre d'être prêt, parler trop vague, vendre trop tôt, changer de méthode.
3. Choisir UNE vérité utile qui pique mais aide.
4. Transformer cette vérité en conseil simple, mémorable, sauvegardable.
5. Écrire en phrases courtes, respirantes, avec une tension dès la première ligne.

STYLE À PRODUIRE
- Mobile-first.
- Phrases courtes.
- Beaucoup de respiration.
- Une idée forte.
- Pas plus de 120 à 170 mots pour un post Instagram/Facebook.
- Ton direct, humain, premium, sans agression.
- Spécifique au contexte utilisateur.
- Si MRR / produits digitaux : parler de formations achetées, page blanche, publication, tunnel, vente, audience silencieuse, exécution.
- Si coaching/service : parler de crédibilité, expertise, confiance, peur de vendre, message trop flou.
- Si e-commerce : parler de désir, preuve, offre, décision, objections.

TEST QUALITÉ AVANT SORTIE
Si le contenu ressemble à une réponse ChatGPT générique, réécris mentalement.
Si le hook pourrait aller sur n'importe quel sujet, réécris.
Si le conseil tient en « sois authentique » ou « écoute ton audience », réécris.
Si le post n'a pas une phrase que l'audience pourrait sauvegarder, réécris.

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

    category_line = "Donne un conseil utile, spécifique, sauvegardable."
    if "algorith" in category:
        category_line = "Explique un principe algorithme terrain avec une action simple : hook, rétention, sauvegarde, commentaire, timing ou recyclage. Aucun cours."
    elif "viral" in category:
        category_line = "Crée une vérité relatable, partageable, avec une phrase mémorable. Pas de buzz vide."
    elif "conversion" in category or "vente" in category or "convert" in goal:
        category_line = "Crée une prise de conscience qui rapproche le lecteur d'une décision, sans vendre lourdement."
    elif "mrr" in category or "MRR" in market:
        category_line = "Parle au débutant MRR / produits digitaux qui consomme, hésite, publie peu, veut vendre mais reste bloqué."

    if "tiktok" in network or "reel" in fmt:
        format_line = "Format vidéo court : phrases très courtes, 1 idée par ligne, hook en 2 secondes."
        max_words = "90 à 130 mots maximum."
    elif "linkedin" in network:
        format_line = "Format LinkedIn : autorité calme, point de vue net, mais pas d'article lourd."
        max_words = "140 à 220 mots maximum."
    elif "story" in fmt:
        format_line = "Format Story : ultra court, impact immédiat, très peu de texte."
        max_words = "45 à 80 mots maximum."
    else:
        format_line = "Format Instagram/Facebook post : lisible sur mobile, lignes courtes, respiration, punchline utile."
        max_words = "100 à 170 mots maximum."

    return f"""
CADRE QUALITÉ SPÉCIFIQUE
- Marché : {market}
- Angle prioritaire : {category_line}
- Adaptation format : {format_line}
- Longueur : {max_words}

STRUCTURE RECOMMANDÉE POUR POST SIMPLE
1. Première ligne = vérité qui accroche.
2. 2 à 4 lignes de situation concrète.
3. Une phrase de déclic.
4. Un conseil simple.
5. Une phrase mémorable.
6. CTA humain optionnel.

EXEMPLES DE STYLE AUTORISÉ
- « Tu consommes plus de contenu que tu n'en publies. »
- « Le problème, ce n'est pas ton manque d'idées. C'est que tu changes d'angle avant d'avoir testé le premier. »
- « Un contenu imparfait publié bat une idée parfaite restée dans ta tête. »
- « Si ton audience ne comprend pas ton message en 3 secondes, elle ne va pas deviner la suite. »

EXEMPLES DE STYLE INTERDIT
- « Vous méritez de réussir. »
- « Connectez-vous à votre audience. »
- « Optimisez votre stratégie marketing. »
- « Créez du contenu authentique. »
""".strip()


def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    fmt = _clean(payload.get("format"), "post").lower()
    seed = random.randint(10000, 999999)

    if fmt == "carrousel":
        blocks_rule = "Retourne 6 blocks role='slide' + 1 block role='cta'. Texte court par slide. Pas de paragraphe."
    elif fmt == "reel":
        blocks_rule = "Retourne 1 block role='hook', 1 block role='body' sous forme de script vidéo respirant, 1 block role='cta'."
    else:
        blocks_rule = "Retourne exactement 3 blocks : role='hook', role='body', role='cta'. Le body doit rester court, aéré, mobile-first."

    return f"""
{_context_prompt(payload)}

{_quality_frame(payload)}

VARIATION LIVE
Seed créatif : {seed}
Tu dois produire un angle différent des générations précédentes.

CONTRAINTE PRINCIPALE
Écris comme si l'utilisateur allait copier-coller le contenu dans Instagram maintenant.
Pas de théorie.
Pas de phrase générique.
Pas de mini-article.
Pas de motivation creuse.

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
Le contenu suivant est refusé car il est trop générique, trop lourd ou trop motivationnel :

{_clip(bad_text, 1800)}

Réécris-le entièrement.

{_context_prompt(payload)}

RÈGLES DE RÉÉCRITURE
- Fais court.
- Fais spécifique.
- Fais mobile-first.
- Commence par une vérité concrète.
- Évite absolument : vous méritez, croyez en vous, passez à l'action, contenu authentique, écoutez votre audience, optimisez votre stratégie.
- Si le brief concerne MRR / business digital : parle d'exécution réelle, publication, page blanche, formations achetées, audience silencieuse, ventes irrégulières.
- Donne une seule idée forte.

JSON STRICT avec blocks hook/body/cta.
""".strip()


def _plan_90_user_prompt(payload: Dict[str, Any]) -> str:
    return f"""
{_context_prompt(payload)}

MISSION : PLAN 90 JOURS DE CONSEILS EXPERTS
Crée un calendrier de 90 jours pour que l'utilisateur puisse conseiller son audience et devenir une personne intéressante à suivre.
Ne génère PAS 90 posts complets.
Génère 90 angles forts, variés, actionnables, non répétitifs.

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
- Alterne : conseil d'autorité, erreur fréquente, algorithme, viralité douce, objection, conversion, storytelling, lead magnet, régularité, recyclage, CTA, preuve, confiance, anti-page blanche.
- Chaque hook_seed doit déjà être spécifique et publiable.
- Jamais LGD, jamais marque interne.

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
        top_p=0.92,
        frequency_penalty=0.72,
        presence_penalty=0.65,
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


def generate_social_ai_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _single_generation_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=1600, temperature=0.88 + random.random() * 0.07)
    data = _sanitize_payload_text(data)
    blocks = _normalize_blocks(data.get("blocks"))

    full_text = _flat_text_from_blocks(blocks)
    if _looks_weak(full_text):
        repair_prompt = _repair_user_prompt(safe_payload, full_text)
        data = _generate_json(repair_prompt, max_tokens=1450, temperature=0.94)
        data = _sanitize_payload_text(data)
        blocks = _normalize_blocks(data.get("blocks"))

    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai_true_brain_v4_final_mobile_first",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post court mobile-first ou Reel selon le réseau."),
            "publish_tip": _clean(performance.get("publish_tip"), "Publie quand ton audience est disponible, puis compare les réponses qualifiées plutôt que les likes."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "La première ligne doit faire comprendre en 3 secondes pourquoi le lecteur est concerné."),
            "visual_idea": _clean(performance.get("visual_idea"), "Une phrase forte en grand, peu de texte, contraste lisible."),
            "variation_idea": _clean(performance.get("variation_idea"), "Réécris le même angle avec une objection ou une situation concrète différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _plan_90_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=6500, temperature=0.82)
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
        "mode": "live_ai_90_day_plan_v4_final",
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
            "Génère maintenant le post complet de ce jour. Fais court, spécifique, mobile-first, non générique.",
        ]
    ).strip()
    return generate_social_ai_live(merged)
