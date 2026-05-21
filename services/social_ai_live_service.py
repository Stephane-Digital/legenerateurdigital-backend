from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List, Literal

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

SocialRole = Literal["hook", "body", "cta", "slide", "title"]


class SocialAILiveError(RuntimeError):
    pass


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").replace("\r", "").strip()
    return text or fallback


def _clip(value: Any, limit: int = 4000) -> str:
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


def _normalize_blocks(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

    allowed = {"hook", "body", "cta", "slide", "title"}
    blocks: List[Dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role"), "body").lower()
        text = _clean(item.get("text"))
        if role not in allowed:
            role = "body"
        if text:
            text = _strip_post_labels(text)
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


def _strip_post_labels(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"(?im)^\s*(HOOK|BODY|CTA|TITRE|LÉGENDE|LEGENDE|SLIDE\s*\d*|POST|CAPTION)\s*[:：-]\s*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _forbidden_brand_filter(text: str, allowed_offer: str = "") -> str:
    """Empêche la marque interne d'apparaître sauf si l'utilisateur l'a explicitement donnée."""
    allowed = "lgd" in allowed_offer.lower() or "générateur digital" in allowed_offer.lower() or "generateur digital" in allowed_offer.lower()
    if allowed:
        return text

    cleaned = re.sub(r"\bLe\s+G[eé]n[eé]rateur\s+Digital\b", "ton offre", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bLGD\b", "ton offre", cleaned, flags=re.IGNORECASE)
    return cleaned


def _sanitize_payload_text(data: Dict[str, Any]) -> Dict[str, Any]:
    offer = _clean(data.get("offer") or data.get("product") or data.get("subject"))

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return _forbidden_brand_filter(_strip_post_labels(value), offer)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    return walk(data)


def _system_prompt() -> str:
    return """
Tu es SOCIAL AI V2 — cerveau premium de contenu social LIVE.

IDENTITÉ MÉTIER
Tu réunis 5 expertises :
1. copywriter senior direct-response,
2. stratège social media spécialisé marketing digital / business en ligne / MRR / coaching / services / produits digitaux,
3. psychologue comportemental orienté achat et passage à l'action,
4. créateur de contenu capable de produire du contenu humain, utile, crédible et partageable,
5. expert algorithmes terrain : hook, rétention, commentaires qualifiés, sauvegardes, répétition, recyclage.

RÈGLE ABSOLUE MARQUE
Tu ne mentionnes jamais LGD, Le Générateur Digital, une plateforme interne, un outil ou une marque non explicitement fournie par l'utilisateur.
L'utilisateur final doit apparaître comme l'expert utile auprès de SON audience.
La marque interne est invisible. Le contenu parle toujours du produit, de l'audience, de la douleur et du résultat de l'utilisateur.

MISSION COMMERCIALE
Produire un contenu qui donne envie à l'utilisateur de dire : « je peux poster ça maintenant ».
Le contenu doit créer un vrai effet : « c'est exactement ce que mon audience vit ».
Tu dois aider l'utilisateur à prodiguer des conseils à son audience, paraître crédible, créer confiance, autorité, commentaires, leads et ventes.

INTERDICTIONS TOTALES
- Pas de phrases génériques : « il est essentiel de », « dans le monde d'aujourd'hui », « découvrez comment », « contenu authentique », « connectez-vous avec votre audience », « apportez de la valeur ».
- Pas de conseil bateau : écouter son audience, être authentique, publier régulièrement, comprendre ses besoins, optimiser sa stratégie.
- Pas de ton corporate, pas de LinkedIn mou, pas de coach bullshit, pas de blabla théorique.
- Pas de labels dans le contenu final : pas de HOOK:, BODY:, CTA:.
- Pas de promesses magiques, pas de faux chiffres, pas de faux témoignages.
- Pas de « nous », « notre », « votre outil », sauf si l'utilisateur le demande clairement.

MÉTHODE INVISIBLE OBLIGATOIRE
Avant d'écrire, tu fais mentalement ceci :
1. Traduire le brief flou en situation concrète.
2. Identifier la douleur émotionnelle exacte : fatigue, dispersion, honte, surcharge, page blanche, peur de vendre, manque de clarté, ventes irrégulières.
3. Choisir une tension qui arrête le scroll.
4. Donner UNE idée forte, pas dix conseils moyens.
5. Écrire avec scènes concrètes, phrases courtes, respiration, contraste, vérité utile.
6. Finir par un CTA naturel adapté à l'objectif.

QUALITÉ ATTENDUE
Le post doit être spécifique, humain, net, premium, publiable, utile, non générique.
Chaque génération doit avoir un angle différent, même sur le même sujet.
Si le brief est vague, tu infères une situation concrète dans le marketing digital ou le business en ligne.

SORTIE TECHNIQUE
Réponds uniquement en JSON valide, sans markdown, sans texte hors JSON.
""".strip()


def _context_prompt(payload: Dict[str, Any]) -> str:
    return f"""
CONTEXTE UTILISATEUR
- Format demandé : {_clean(payload.get('format'), 'post')}
- Réseau : {_clean(payload.get('network'), 'Instagram')}
- Objectif : {_clean(payload.get('goal') or payload.get('objective'), 'Autorité')}
- Catégorie : {_clean(payload.get('category'), 'Conseils')}
- Ton : {_clean(payload.get('tone'), 'Premium humain')}
- Offre / produit / sujet : {_clip(payload.get('offer') or payload.get('product') or payload.get('subject') or payload.get('prompt'), 1200)}
- Audience : {_clip(payload.get('audience') or payload.get('target'), 1200)}
- Douleur : {_clip(payload.get('pain'), 1200)}
- Promesse / résultat : {_clip(payload.get('promise') or payload.get('result'), 1200)}
- Objection : {_clip(payload.get('objection'), 800)}
- CTA souhaité : {_clip(payload.get('cta'), 500)}
- Brief libre : {_clip(payload.get('prompt') or payload.get('brief') or payload.get('context'), 2500)}

INTERPRÉTATION SI CONTEXTE FLOU
Si l'utilisateur donne seulement une idée vague, transforme-la en contenu concret pour entrepreneur / créateur / vendeur de produit digital.
Ne reste jamais abstrait. Utilise le vécu réel : page blanche, trop de conseils, trop d'outils, fatigue de publier, peur de mal faire, ventes irrégulières, audience silencieuse.
""".strip()


def _quality_frame(category: str, network: str, fmt: str) -> str:
    cat = category.lower()
    net = network.lower()
    fmt_l = fmt.lower()

    if "algorith" in cat:
        category_rules = """
ANGLE PRIORITAIRE : CONSEIL ALGORITHME TERRAIN
Tu dois expliquer un principe concret : premières lignes, rétention, watch time, sauvegardes, commentaires qualifiés, recyclage, régularité ou timing.
Mais tu ne fais jamais un cours. Tu écris un post que l'utilisateur peut publier pour conseiller son audience.
Le conseil doit être actionnable aujourd'hui.
""".strip()
    elif "viral" in cat:
        category_rules = """
ANGLE PRIORITAIRE : VIRALITÉ DOUCE
Tu dois produire une vérité partageable, relatable, qui crée un « moi aussi ».
Pas de putaclic. Pas de buzz vide.
Le contenu doit contenir une phrase mémorable que l'audience pourrait sauvegarder ou partager.
""".strip()
    elif "conseil" in cat:
        category_rules = """
ANGLE PRIORITAIRE : CONSEIL D'AUTORITÉ
Tu dois donner un conseil qui fait paraître l'utilisateur crédible dans sa niche.
Une idée forte. Une correction simple. Une action claire.
Le lecteur doit repartir avec : « je sais quoi faire maintenant ».
""".strip()
    elif "conversion" in cat or "vente" in cat:
        category_rules = """
ANGLE PRIORITAIRE : CONVERSION / VENTE DOUCE
Tu dois créer désir, confiance et prochaine action, sans pousser lourdement.
Le contenu doit faire comprendre pourquoi agir maintenant est logique.
""".strip()
    elif "hook" in cat:
        category_rules = """
ANGLE PRIORITAIRE : HOOKS PSYCHOLOGIQUES
Tu dois générer des ouvertures qui nomment une tension précise dès la première ligne.
Chaque hook doit être court, humain, spécifique et difficile à ignorer.
""".strip()
    else:
        category_rules = """
ANGLE PRIORITAIRE : CONTENU UTILE ET CONVERSIONNEL
Tu dois combiner tension, conseil, clarté, crédibilité et CTA naturel.
""".strip()

    if "tiktok" in net or "reel" in fmt_l:
        network_rules = """
ADAPTATION RÉSEAU
Phrases très courtes. Pattern interrupt. Rythme vidéo. Une idée par phrase. Pas de paragraphe lourd.
""".strip()
    elif "linkedin" in net:
        network_rules = """
ADAPTATION RÉSEAU
Autorité calme, point de vue net, crédibilité business, pas de punchline cheap.
""".strip()
    elif "facebook" in net:
        network_rules = """
ADAPTATION RÉSEAU
Conversation naturelle, proximité, sensation de parler à une vraie personne.
""".strip()
    else:
        network_rules = """
ADAPTATION RÉSEAU
Instagram / multi-réseaux : lisible, émotionnel, sauvegardable, visuel, facile à lire sur mobile.
""".strip()

    return f"{category_rules}\n\n{network_rules}"


def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    format_txt = _clean(payload.get("format"), "post").lower()
    network = _clean(payload.get("network"), "Instagram")
    category = _clean(payload.get("category"), "Conseils")

    if format_txt == "carrousel":
        expected = "6 à 8 blocks avec role='slide'. Chaque slide doit être courte, visuelle, forte, sans phrase molle. Dernier block role='cta'."
        structure = "Slide 1 tension / Slide 2 vécu / Slide 3 erreur / Slide 4 vérité / Slide 5 méthode / Slide 6 action / Slide 7 CTA si utile."
    elif format_txt == "reel":
        expected = "1 hook très court + 1 body sous forme de script vidéo rythmé + 1 cta optionnel."
        structure = "Ouverture choc 2 secondes, scène relatable, tension, déclic, action, CTA court."
    else:
        expected = "1 hook + 1 body + 1 cta naturel."
        structure = "Hook précis, tension vécue, vérité utile, conseil concret, action simple, CTA naturel."

    seed = random.randint(1000, 999999)

    return f"""
{_context_prompt(payload)}

{_quality_frame(category, network, format_txt)}

VARIATION LIVE
Seed créatif : {seed}
Même si le sujet ressemble à une génération précédente, tu dois changer l'angle, les exemples, la tension et le CTA.

OBJECTIF QUALITÉ IMMÉDIAT
Ne produis pas un texte « correct ».
Produis un texte que l'utilisateur peut poster avec fierté.
Le lecteur doit ressentir : « cette personne comprend exactement mon problème ».

TEST ANTI-GÉNÉRIQUE
Avant de répondre, vérifie mentalement :
- Est-ce que ce post pourrait être publié par n'importe qui ? Si oui, réécris.
- Est-ce qu'il contient une vérité concrète ? Sinon, réécris.
- Est-ce qu'il donne un conseil précis ou une prise de conscience utile ? Sinon, réécris.
- Est-ce qu'il évite les phrases bateau ? Sinon, réécris.

STRUCTURE ATTENDUE
{structure}

ATTENDU BLOCKS
{expected}

CONSEIL DE PERFORMANCE SÉPARÉ
Ajoute une section performance séparée, non destinée au canvas :
- recommended_format
- publish_tip
- algorithm_tip
- visual_idea
- variation_idea

JSON STRICT
{{
  "title": "titre court interne",
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


def _plan_90_user_prompt(payload: Dict[str, Any]) -> str:
    return f"""
{_context_prompt(payload)}

MISSION SPÉCIALE : PLAN 90 JOURS CONSEILS EXPERTS
Crée un calendrier stratégique de 90 jours pour aider l'utilisateur à conseiller son audience et devenir une personne intéressante à suivre.
Ne génère pas 90 posts complets.
Génère 90 jours d'angles précis, variés, actionnables, non répétitifs.

RÈGLES DU PLAN
- 90 jours exactement.
- Aucun doublon d'angle.
- Chaque jour doit pouvoir devenir un post LIVE IA fort.
- Alterner : conseils d'autorité, algorithmes, viralité douce, erreurs, objections, conversion, storytelling, lead magnet, confiance, action simple, régularité, timing, recyclage, CTA, preuve, persona, anti-page blanche.
- Chaque jour doit aider l'audience avec un conseil concret.
- Ne mentionne jamais LGD ou une marque non donnée par l'utilisateur.

QUALITÉ DES JOURS
Chaque hook_seed doit déjà donner envie de cliquer.
Chaque audience_benefit doit être tangible.
Chaque algorithm_tip doit être simple, prudent et applicable.

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
        top_p=0.94,
        frequency_penalty=0.55,
        presence_penalty=0.45,
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
    data = _generate_json(prompt, max_tokens=1900, temperature=0.92 + random.random() * 0.05)
    data = _sanitize_payload_text(data)

    blocks = _normalize_blocks(data.get("blocks"))
    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai_true_brain_v2",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post court ou Reel selon le réseau."),
            "publish_tip": _clean(performance.get("publish_tip"), "Teste deux créneaux proches et garde celui qui déclenche le plus de réponses qualifiées."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "Les premières lignes doivent créer une raison claire de rester."),
            "visual_idea": _clean(performance.get("visual_idea"), "Visuel simple avec une phrase forte en grand."),
            "variation_idea": _clean(performance.get("variation_idea"), "Reposte le même angle avec une objection différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _plan_90_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=6200, temperature=0.84)
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
        "mode": "live_ai_90_day_plan_true_brain_v2",
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
            "Génère maintenant le post complet de ce jour avec un angle différent, concret et publiable.",
        ]
    ).strip()
    return generate_social_ai_live(merged)
