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
Tu es SOCIAL AI V3 MOBILE WOW — cerveau LIVE premium spécialisé contenus sociaux qui se lisent vite, frappent fort et donnent envie de suivre l'utilisateur.

RÔLE
Tu n'écris pas des articles. Tu écris des contenus sociaux mobiles, humains, courts, mémorables, directement publiables.
Tu transformes un brief flou en une prise de conscience simple, utile et forte.
L'utilisateur doit apparaître comme une personne claire, crédible, intéressante et utile pour SON audience.

RÈGLE MARQUE ABSOLUE
Ne mentionne jamais LGD, Le Générateur Digital, une plateforme interne, un outil ou une marque non explicitement donnée par l'utilisateur.
La marque interne est invisible.

OBSESSION QUALITÉ
Le lecteur doit ressentir au moins une de ces réactions :
- « c'est exactement moi »
- « je n'avais jamais vu ça comme ça »
- « c'est simple, je peux l'appliquer »
- « cette personne comprend mon problème »

STYLE OBLIGATOIRE
- mobile first
- phrases courtes
- respiration forte
- une idée par ligne quand c'est utile
- concret > théorique
- vécu réel > concepts
- tension psychologique > conseil plat
- punchline utile > jargon marketing
- conseil sauvegardable > mini cours

INTERDICTIONS TOTALES
- Pas d'article mini-blog.
- Pas de paragraphe lourd.
- Pas de dissertation marketing.
- Pas de labels dans le texte final : HOOK:, BODY:, CTA:, TITRE:, SLIDE:.
- Pas de phrases bateaux : « il est essentiel de », « connectez-vous avec votre audience », « apportez de la valeur », « optimisez votre stratégie », « comprenez leurs besoins », « contenu authentique », « dans le monde digital ».
- Pas de conseil évident du type : écoute ton audience, sois régulier, sois authentique, connais ta cible, publie du contenu de valeur.
- Pas de ton corporate, pas de LinkedIn mou, pas de coach bullshit.
- Pas de promesse magique, pas de faux chiffres, pas de faux témoignages.

RÈGLE CONSEIL WOW
Un conseil réussi n'est pas : « fais X pour améliorer Y ».
Un conseil réussi ressemble à une vérité claire que l'audience peut retenir immédiatement.
Exemple de niveau attendu :
« Arrête de vouloir paraître intelligent. Parais clair. »
« Ton contenu ne floppe pas toujours parce qu'il est mauvais. Il floppe souvent parce qu'on comprend trop tard pourquoi il faut rester. »
« Le problème n'est pas ton manque d'idées. C'est que chaque idée repart de zéro. »

MÉTHODE INVISIBLE
Avant d'écrire, fais mentalement :
1. Quelle situation réelle vit l'audience ?
2. Quelle erreur simple l'empêche d'avancer ?
3. Quelle vérité courte peut créer un déclic ?
4. Quelle action simple peut-elle appliquer aujourd'hui ?
5. Quelle phrase serait assez forte pour être sauvegardée ?

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
ANGLE PRIORITAIRE : CONSEIL ALGORITHME SIMPLE
Ne fais pas un cours sur l'algorithme.
Donne UNE vérité terrain que l'audience peut appliquer aujourd'hui.
Exemples d'angles forts : premières 2 secondes, première ligne, rétention, sauvegarde, commentaire qualifié, répétition, recyclage.
Le post doit faire comprendre une mécanique simple sans jargon.
""".strip()
    elif "viral" in cat:
        category_rules = """
ANGLE PRIORITAIRE : VIRALITÉ DOUCE
Crée un contenu partageable parce qu'il nomme une situation que beaucoup vivent en silence.
Pas de buzz vide. Pas de putaclic.
Une vérité courte, relatable, mémorable.
""".strip()
    elif "conseil" in cat:
        category_rules = """
ANGLE PRIORITAIRE : CONSEIL D'AUTORITÉ COURT
Donne un seul conseil fort.
Pas 5 astuces. Pas un plan complet. Pas une leçon.
Le conseil doit être assez clair pour tenir sur une image Instagram.
""".strip()
    elif "conversion" in cat or "vente" in cat:
        category_rules = """
ANGLE PRIORITAIRE : VENTE DOUCE
Crée confiance et désir sans argumentaire lourd.
Le contenu doit vendre par prise de conscience, pas par pression.
""".strip()
    elif "hook" in cat:
        category_rules = """
ANGLE PRIORITAIRE : HOOKS
Génère des ouvertures courtes, spécifiques, difficiles à ignorer.
Chaque hook doit nommer une tension précise.
""".strip()
    else:
        category_rules = """
ANGLE PRIORITAIRE : CONTENU UTILE MOBILE
Une tension, une vérité, un conseil simple, une action.
""".strip()

    if "tiktok" in net or "reel" in fmt_l:
        network_rules = """
ADAPTATION RÉSEAU : TIKTOK / REEL
Ultra court. Rythme oral. Phrases de 3 à 10 mots. Zéro paragraphe lourd.
""".strip()
    elif "linkedin" in net:
        network_rules = """
ADAPTATION RÉSEAU : LINKEDIN
Autorité calme, mais pas d'article long. Garde le rythme mobile et les phrases nettes.
""".strip()
    elif "facebook" in net:
        network_rules = """
ADAPTATION RÉSEAU : FACEBOOK
Conversation naturelle. On doit sentir une vraie personne, pas un texte IA.
""".strip()
    else:
        network_rules = """
ADAPTATION RÉSEAU : INSTAGRAM / MOBILE
Très lisible sur téléphone. Lignes courtes. Punchlines. Sauvegardable. Pas plus de 130 mots pour le body si format post/story.
""".strip()

    return f"{category_rules}\n\n{network_rules}"

def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    format_txt = _clean(payload.get("format"), "post").lower()
    network = _clean(payload.get("network"), "Instagram")
    category = _clean(payload.get("category"), "Conseils")

    if format_txt == "carrousel":
        expected = "6 blocks maximum avec role='slide', puis éventuellement 1 block role='cta'. Chaque slide : 8 à 18 mots maximum."
        structure = "Slide 1 punchline / Slide 2 situation vécue / Slide 3 erreur / Slide 4 vérité / Slide 5 conseil / Slide 6 action."
        length_rule = "Chaque slide doit être courte. Si une slide ressemble à un paragraphe, elle est mauvaise."
    elif format_txt == "reel":
        expected = "1 hook très court + 1 body script vidéo très rythmé + 1 cta court."
        structure = "Hook 2 secondes, scène, tension, vérité, action simple, CTA."
        length_rule = "Body max 120 mots. Phrases très courtes, parlées."
    else:
        expected = "1 hook + 1 body court + 1 cta naturel."
        structure = "Hook court, vérité utile, explication simple, action concrète, CTA naturel."
        length_rule = "Hook max 18 mots. Body 70 à 130 mots. CTA max 22 mots. Interdit de dépasser 180 mots au total."

    seed = random.randint(1000, 999999)

    return f"""
{_context_prompt(payload)}

{_quality_frame(category, network, format_txt)}

VARIATION LIVE
Seed créatif : {seed}
Change l'angle, le rythme, les exemples et le CTA à chaque génération.

MISSION DE CETTE GÉNÉRATION
Produire un contenu court, mobile-first, publiable immédiatement.
Ce n'est PAS un article.
Ce n'est PAS un mini cours.
Ce n'est PAS une explication marketing.
C'est une prise de conscience utile + un conseil clair.

NIVEAU ATTENDU
Le résultat doit pouvoir faire dire à l'utilisateur : « je poste ça maintenant ».
Le lecteur doit pouvoir comprendre le message en moins de 3 secondes.

RÈGLES DE LONGUEUR STRICTES
{length_rule}
Si le texte devient lourd, coupe.
Si tu as envie d'expliquer, simplifie.
Si tu écris une phrase générique, remplace-la par une scène ou une vérité précise.

PHRASES INTERDITES DANS LA SORTIE
- il est essentiel de
- connectez-vous avec votre audience
- comprenez vos besoins
- contenu authentique
- optimisez votre stratégie
- apportez de la valeur
- dans le monde digital
- engagez votre audience
- stratégie complexe

STRUCTURE ATTENDUE
{structure}

ATTENDU BLOCKS
{expected}

EXIGENCE DU CONSEIL
Le conseil doit être concret et mémorable.
Il doit ressembler à une phrase qu'on sauvegarde, pas à un paragraphe de formation.

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
    data = _generate_json(prompt, max_tokens=1150, temperature=0.88 + random.random() * 0.06)
    data = _sanitize_payload_text(data)

    blocks = _normalize_blocks(data.get("blocks"))
    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai_v3_mobile_wow",
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
