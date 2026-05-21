from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List, Literal, Optional

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
            return _forbidden_brand_filter(value, offer)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    return walk(data)


def _system_prompt() -> str:
    return """
Tu es un stratège social media senior spécialisé marketing digital, copywriting comportemental, contenu d'autorité, algorithmes, viralité propre, conversion et vente douce.

RÈGLE ABSOLUE
Tu ne mentionnes jamais LGD, Le Générateur Digital, une plateforme interne, un outil ou une marque non fournie explicitement par l'utilisateur.
L'utilisateur final doit apparaître comme l'expert utile auprès de SON audience.

MISSION
Produire du contenu qui fait dire : « ce post comprend exactement mon audience ».
Le contenu doit libérer l'utilisateur de la page blanche, l'aider à prodiguer des conseils crédibles à son audience, construire confiance, autorité, engagement et ventes.

STYLE
Humain, spécifique, premium, net, utile, jamais corporate, jamais générique, jamais bullshit guru.
Pas de titres techniques dans le post final : pas de HOOK:, BODY:, CTA:.
Pas de phrases IA classiques comme « dans le monde d'aujourd'hui », « il est essentiel de », « découvrez comment ».

MÉTHODE INVISIBLE
1. Identifier la tension émotionnelle exacte.
2. Trouver l'angle le plus utile : conseil, erreur, déclic, algorithme, viralité, objection, conversion ou storytelling.
3. Écrire un contenu directement publiable.
4. Ajouter une recommandation de performance séparée, jamais injectée dans le post.

FORMAT DE RÉPONSE
Réponds uniquement en JSON valide, sans markdown.
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

EXIGENCE QUALITÉ
Le contenu doit être précis, publiable immédiatement, orienté résultat tangible et assez fort pour justifier un abonnement mensuel.
Si le brief est flou, infère intelligemment une audience marketing digital / business en ligne, mais reste utile et concret.
""".strip()


def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    format_txt = _clean(payload.get("format"), "post").lower()
    category = _clean(payload.get("category"), "Conseils")

    if format_txt == "carrousel":
        expected = "6 à 8 blocks avec role='slide', chaque slide courte, visuelle et forte. Dernier block role='cta'."
    elif format_txt == "reel":
        expected = "1 hook très court + 1 body sous forme de script vidéo rythmé + 1 cta optionnel."
    else:
        expected = "1 hook + 1 body + 1 cta naturel si utile."

    return f"""
{_context_prompt(payload)}

TYPE DE GÉNÉRATION
Génère un contenu LIVE IA dans la catégorie : {category}.

ATTENDU BLOCKS
{expected}

CONSEIL DE PERFORMANCE
Ajoute une section performance séparée avec :
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

MISSION SPÉCIALE
Crée un calendrier stratégique de 90 jours de conseils à donner à l'audience.
Chaque jour doit avoir un angle différent. Ne génère pas 90 posts complets.
Le plan doit donner envie de revenir chaque jour générer le post LIVE.

RÈGLES DU PLAN
- 90 jours exactement.
- Aucun doublon d'angle.
- Alterner : conseils d'autorité, algorithmes, viralité douce, erreurs, objections, conversion, storytelling, lead magnet, confiance, action simple.
- Chaque jour doit être concret et orienté résultat.
- Ne mentionne jamais LGD ou une marque non donnée par l'utilisateur.

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
        frequency_penalty=0.35,
        presence_penalty=0.25,
        max_tokens=max_tokens,
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
    data = _generate_json(prompt, max_tokens=1500, temperature=0.88 + random.random() * 0.04)
    data = _sanitize_payload_text(data)

    blocks = _normalize_blocks(data.get("blocks"))
    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post court ou Reel selon le réseau."),
            "publish_tip": _clean(performance.get("publish_tip"), "Teste deux créneaux et garde celui qui déclenche le plus de réponses qualifiées."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "Les premières lignes doivent créer une raison claire de rester."),
            "visual_idea": _clean(performance.get("visual_idea"), "Visuel simple avec une phrase forte en grand."),
            "variation_idea": _clean(performance.get("variation_idea"), "Reposte le même angle avec une objection différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _plan_90_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=5200, temperature=0.78)
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
        "mode": "live_ai_90_day_plan",
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
        ]
    ).strip()
    return generate_social_ai_live(merged)
