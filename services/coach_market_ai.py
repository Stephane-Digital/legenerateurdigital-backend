from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


REQUIRED_KEYS = (
    "id",
    "title",
    "badge",
    "demand",
    "score",
    "why",
    "product",
    "price",
    "offerDescription",
    "problemSolved",
    "transformationPromise",
    "targetAudienceDescription",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    raw = _clean(value).lower()
    raw = raw.replace("é", "e").replace("è", "e").replace("ê", "e")
    raw = raw.replace("à", "a").replace("â", "a").replace("ù", "u")
    raw = raw.replace("î", "i").replace("ï", "i").replace("ô", "o")
    raw = raw.replace("ç", "c")
    raw = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return raw[:64] or "opportunite_live"


def _safe_json_loads(text: str) -> Dict[str, Any]:
    raw = _clean(text)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_usage(usage: Any) -> Optional[Dict[str, int]]:
    try:
        if not usage:
            return None
        prompt_tokens = int(getattr(usage, "prompt_tokens", None) or usage.get("prompt_tokens") or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", None) or usage.get("completion_tokens") or 0)
        total_tokens = int(getattr(usage, "total_tokens", None) or usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
    except Exception:
        return None


def _fallback_opportunities() -> List[Dict[str, Any]]:
    return [
        {
            "id": "live_reconversion_45_plus",
            "title": "Reconversion professionnelle 45+",
            "badge": "Demande très forte",
            "demand": "Salariés, indépendants fragilisés, personnes en transition",
            "score": 96,
            "why": "Marché émotionnel avec besoin urgent de sécurité, de clarté et de revenu complémentaire.",
            "product": "Formation courte + plan 30 jours + templates d’action",
            "price": "197€ à 497€",
            "offerDescription": "Un programme digital pour aider les personnes de 45 ans et plus à construire progressivement une activité en ligne réaliste et compatible avec leur vie actuelle.",
            "problemSolved": "Aider des personnes expérimentées mais inquiètes à transformer leur vécu ou leurs compétences en projet digital concret sans risque brutal.",
            "transformationPromise": "Passer d’une inquiétude professionnelle à un plan clair pour créer une première offre digitale et préparer un revenu complémentaire.",
            "targetAudienceDescription": "Avatar : Sophie, 49 ans. Elle veut sécuriser son avenir, manque de clarté, craint la technique et cherche une méthode rassurante, simple et guidée.",
        },
        {
            "id": "live_ia_solopreneurs",
            "title": "IA pour indépendants et petites entreprises",
            "badge": "Potentiel IA énorme",
            "demand": "Freelances, artisans, consultants, TPE",
            "score": 94,
            "why": "Forte demande pour gagner du temps, créer du contenu et vendre sans recruter.",
            "product": "Mini-formation IA + prompts prêts à l’emploi + cas pratiques",
            "price": "97€ à 297€",
            "offerDescription": "Une formation pratique qui aide les indépendants à utiliser l’IA pour créer du contenu, structurer leurs offres et améliorer leur communication commerciale.",
            "problemSolved": "Aider les professionnels débordés à appliquer l’IA à leur activité réelle sans jargon ni complexité.",
            "transformationPromise": "Passer d’un usage confus de l’IA à un système simple de prompts, contenus et actions commerciales utilisables chaque semaine.",
            "targetAudienceDescription": "Avatar : Julien, 38 ans. Indépendant compétent, débordé par la communication, il veut utiliser l’IA concrètement sans perdre du temps.",
        },
        {
            "id": "live_marketing_digital_debutants",
            "title": "Marketing digital simplifié pour débutants",
            "badge": "Compatible LGD à 100%",
            "demand": "Débutants, MRR, affiliés, créateurs de contenu",
            "score": 93,
            "why": "Audience massive avec douleur forte : trop d’informations, pas de méthode, pas de premières ventes.",
            "product": "Méthode simple + calendrier de contenu + tunnel de vente basique",
            "price": "97€ à 397€",
            "offerDescription": "Une méthode digitale simple pour aider les débutants à comprendre le marketing digital, choisir une offre, créer du contenu utile et mettre en place un premier système de vente.",
            "problemSolved": "Aider les débutants à arrêter de consommer des formations dans tous les sens et à suivre une méthode claire vers les premières ventes.",
            "transformationPromise": "Passer d’un débutant perdu à une personne capable de publier, expliquer son offre et ouvrir ses premières conversations de vente.",
            "targetAudienceDescription": "Avatar : Laura, 34 ans. Elle veut gagner de l’argent en ligne, a consommé beaucoup de contenus et cherche enfin une méthode claire et actionnable.",
        },
        {
            "id": "live_email_marketing_independants",
            "title": "Email marketing simple pour indépendants",
            "badge": "Forte valeur business",
            "demand": "Solopreneurs, coachs, formateurs, affiliés",
            "score": 92,
            "why": "L’email reste un levier direct de conversion, mais beaucoup ne savent pas quoi écrire ni quand envoyer.",
            "product": "Séquences email prêtes à adapter + formation courte",
            "price": "97€ à 297€",
            "offerDescription": "Une formation courte pour aider les indépendants à créer une première séquence email simple afin de créer de la confiance et convertir sans écrire comme un copywriter expert.",
            "problemSolved": "Aider les indépendants à ne plus dépendre uniquement des réseaux sociaux et à convertir leurs prospects avec des emails humains.",
            "transformationPromise": "Passer d’une audience dispersée à une séquence email claire qui nourrit la relation, explique l’offre et mène naturellement vers la vente.",
            "targetAudienceDescription": "Avatar : Céline, 39 ans. Elle a une petite audience mais ne sait pas relancer ni vendre par email. Elle veut des modèles simples et humains.",
        },
        {
            "id": "live_faceless_content_ia",
            "title": "Contenu faceless avec IA",
            "badge": "Très forte tendance créateur",
            "demand": "Débutants, créateurs discrets, affiliés, MRR",
            "score": 91,
            "why": "Beaucoup veulent créer du contenu sans montrer leur visage tout en construisant une audience monétisable.",
            "product": "Méthode faceless + prompts + scripts reels + calendrier",
            "price": "47€ à 197€",
            "offerDescription": "Une méthode digitale pour créer du contenu faceless avec l’IA, structurer des scripts courts et publier régulièrement sans se montrer à l’écran.",
            "problemSolved": "Aider les personnes qui n’osent pas se montrer à publier du contenu utile, régulier et monétisable.",
            "transformationPromise": "Passer de la peur de s’exposer à une stratégie de contenu discrète, structurée et capable d’attirer une audience ciblée.",
            "targetAudienceDescription": "Avatar : Manon, 29 ans. Elle veut lancer un projet en ligne mais ne veut pas se filmer. Elle cherche une méthode rassurante compatible avec l’IA.",
        },
    ]


def _normalize_opportunity(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    title = _clean(item.get("title")) or f"Opportunité digitale {index + 1}"

    try:
        score = int(item.get("score") or item.get("opportunityScore") or 80)
    except Exception:
        score = 80
    score = max(0, min(100, score))

    normalized = {
        "id": _clean(item.get("id")) or f"live_{_slug(title)}_{index + 1}",
        "title": title,
        "badge": _clean(item.get("badge")) or "Opportunité IA Live",
        "demand": _clean(item.get("demand")) or "Demande actuelle à préciser",
        "score": score,
        "why": _clean(item.get("why")) or _clean(item.get("reason")) or "Opportunité détectée par Alex IA Live.",
        "product": _clean(item.get("product")) or "Produit digital court et actionnable",
        "price": _clean(item.get("price")) or "97€ à 297€",
        "offerDescription": _clean(item.get("offerDescription")) or _clean(item.get("offer")) or f"Un produit digital autour de {title} pour résoudre un problème précis avec une méthode simple.",
        "problemSolved": _clean(item.get("problemSolved")) or "Aider une audience ciblée à résoudre un problème concret avec une méthode claire et actionnable.",
        "transformationPromise": _clean(item.get("transformationPromise")) or "Passer d’une situation confuse à un plan d’action clair et vendable.",
        "targetAudienceDescription": _clean(item.get("targetAudienceDescription")) or "Avatar prioritaire : personne motivée, bloquée par le manque de méthode, qui cherche une solution simple et rassurante.",
    }

    return normalized


def _normalize_opportunities(data: Dict[str, Any], usage: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    raw = data.get("opportunities") or data.get("items") or data.get("niches") or []
    if not isinstance(raw, list):
        raw = []

    opportunities = []
    for idx, item in enumerate(raw[:5]):
        if isinstance(item, dict):
            opportunities.append(_normalize_opportunity(item, idx))

    if len(opportunities) < 5:
        fallback = _fallback_opportunities()
        existing_ids = {op["id"] for op in opportunities}
        for item in fallback:
            if item["id"] in existing_ids:
                continue
            opportunities.append(item)
            if len(opportunities) >= 5:
                break

    recommended_id = _clean(data.get("recommendedId"))
    if not recommended_id and opportunities:
        recommended_id = str(opportunities[0]["id"])

    response: Dict[str, Any] = {
        "success": True,
        "source": "openai",
        "mode": "live_market",
        "recommendedId": recommended_id,
        "summary": _clean(data.get("summary")) or "Alex a analysé le marché et identifié 5 opportunités digitales à fort potentiel.",
        "opportunities": opportunities[:5],
    }
    if usage:
        response["usage"] = usage
    return response


def _system_prompt(plan: str) -> str:
    plan_n = _clean(plan).lower() or "essentiel"
    return (
        "Tu es Alex Market Analyst IA Live, le moteur d’analyse d’opportunités business de Le Générateur Digital. "
        "Tu dois proposer 5 niches de produits digitaux rentables, demandées et compatibles avec une exécution rapide dans LGD.\n\n"
        f"Plan utilisateur: {plan_n}.\n\n"
        "Tu réponds uniquement en JSON valide, sans markdown, sans texte autour.\n"
        "Structure obligatoire:\n"
        "{\n"
        '  "summary": "résumé court de l’analyse",\n'
        '  "recommendedId": "id_de_la_meilleure_opportunite",\n'
        '  "opportunities": [\n'
        "    {\n"
        '      "id": "slug_unique",\n'
        '      "title": "nom de la niche",\n'
        '      "badge": "badge court",\n'
        '      "demand": "type de demande et audience",\n'
        '      "score": 0,\n'
        '      "why": "pourquoi cette niche est intéressante maintenant",\n'
        '      "product": "produit digital conseillé",\n'
        '      "price": "prix conseillé",\n'
        '      "offerDescription": "description exploitable de l’offre",\n'
        '      "problemSolved": "problème résolu",\n'
        '      "transformationPromise": "transformation promise",\n'
        '      "targetAudienceDescription": "avatar détaillé"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Règles métier:\n"
        "- proposer uniquement des niches éthiques, vendables et compatibles produit digital;\n"
        "- éviter les promesses financières irréalistes;\n"
        "- privilégier les niches avec douleur forte, demande claire, possibilité de contenu social et premier produit simple;\n"
        "- score entre 75 et 99;\n"
        "- offerDescription, problemSolved, transformationPromise et targetAudienceDescription doivent être directement utilisables pour préremplir Coach Alex;\n"
        "- style français naturel, business, concret, premium;\n"
        "- ne pas mentionner que tu n’as pas accès au marché en temps réel; formule comme une analyse IA Live des opportunités actuelles."
    )


def generate_market_opportunities(
    *,
    payload: Dict[str, Any] | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
    plan: str = "essentiel",
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
    if not api_key:
        return {
            "success": False,
            "source": "fallback_no_key",
            "mode": "fallback",
            "recommendedId": "live_reconversion_45_plus",
            "summary": "OpenAI n’est pas configuré. Alex renvoie le fallback premium.",
            "opportunities": _fallback_opportunities(),
        }

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        context = payload if isinstance(payload, dict) else {}

        meta: Dict[str, Any] = {}
        if user_id is not None:
            meta["user_id"] = int(user_id)
        if user_email:
            meta["user_email"] = _clean(user_email)[:120]
        if user_name:
            meta["user_name"] = _clean(user_name)[:80]

        user_payload = {
            "meta": meta,
            "context": context,
            "instruction": (
                "Trouve 5 opportunités de produit digital à forte demande. "
                "Adapte les choix à un utilisateur LGD qui veut créer son propre produit digital. "
                "Optimise pour: demande forte, lancement rapide, contenu social possible, produit vendable entre 27€ et 497€, compatibilité avec Coach Alex, Planner, CMO, Lead Engine et Emailing IA."
            ),
        }

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_COACH_MARKET", os.getenv("OPENAI_MODEL_COACH_LIVE", os.getenv("OPENAI_MODEL_COACH", "gpt-4o-mini"))),
            messages=[
                {"role": "system", "content": _system_prompt(plan)},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)[:14000]},
            ],
            temperature=0.78,
            max_tokens=1800,
            response_format={"type": "json_object"},
        )

        content = ""
        try:
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""

        data = _safe_json_loads(content)
        if not data:
            return {
                "success": False,
                "source": "fallback_empty",
                "mode": "fallback",
                "recommendedId": "live_reconversion_45_plus",
                "summary": "Réponse IA vide. Alex renvoie le fallback premium.",
                "opportunities": _fallback_opportunities(),
            }

        usage = _extract_usage(getattr(resp, "usage", None))
        return _normalize_opportunities(data, usage)

    except Exception as exc:
        return {
            "success": False,
            "source": "fallback_error",
            "mode": "fallback",
            "error": str(exc)[:300],
            "recommendedId": "live_reconversion_45_plus",
            "summary": "Analyse IA Live indisponible. Alex renvoie le fallback premium.",
            "opportunities": _fallback_opportunities(),
        }
