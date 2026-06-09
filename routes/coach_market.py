from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.coach_market_ai import generate_market_opportunities
from services.ai_quota_service import get_or_create_quota, update_quota

try:
    from services.coach_profile_service import read_profile
except Exception:  # pragma: no cover
    read_profile = None  # type: ignore


router = APIRouter(tags=["Coach Market Opportunities"])


class MarketOpportunitiesIn(BaseModel):
    businessModel: Optional[str] = Field(default="offre_digitale", max_length=80)
    business_model: Optional[str] = Field(default=None, max_length=80)
    parcours: Optional[str] = Field(default="creation_produit_digital", max_length=80)
    objective: Optional[str] = Field(default="premiers_revenus", max_length=120)
    level: Optional[str] = Field(default="debutant", max_length=120)
    audienceSize: Optional[str] = Field(default="moins_500", max_length=120)
    mainBlocker: Optional[str] = Field(default="dispersion", max_length=120)
    primaryChannel: Optional[str] = Field(default="instagram", max_length=120)
    count: int = Field(default=5, ge=1, le=8)
    context: Dict[str, Any] = Field(default_factory=dict)
    existingOffer: Optional[str] = Field(default="", max_length=6000)
    prompt: Optional[str] = Field(default="", max_length=12000)


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _user_get(user: Any, key: str, default: Any = None) -> Any:
    """Supporte les deux formes rencontrées en prod: objet SQLAlchemy ou dict."""
    if isinstance(user, dict):
        if key in user:
            return user.get(key, default)
        nested = user.get("user")
        if isinstance(nested, dict):
            return nested.get(key, default)
    return getattr(user, key, default)


def _user_id(user: Any) -> int:
    raw = _user_get(user, "id") or _user_get(user, "user_id") or _user_get(user, "sub")
    uid = _to_int(raw, 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié")
    return uid


def _quota_snapshot(q: Any) -> Dict[str, int]:
    used = _to_int(getattr(q, "tokens_used", None), 0)
    if used == 0 and getattr(q, "used_tokens", None) is not None:
        used = _to_int(getattr(q, "used_tokens", None), 0)

    limit = _to_int(getattr(q, "credits", None), 0)
    if limit == 0 and getattr(q, "tokens_limit", None) is not None:
        limit = _to_int(getattr(q, "tokens_limit", None), 0)
    if limit == 0 and getattr(q, "limit_tokens", None) is not None:
        limit = _to_int(getattr(q, "limit_tokens", None), 0)

    remaining = _to_int(getattr(q, "remaining", None), max(limit - used, 0))
    if remaining <= 0 and limit > 0:
        remaining = max(limit - used, 0)

    return {"used": used, "limit": limit, "remaining": remaining}


def _quota_response(q: Any) -> Dict[str, Any]:
    snap = _quota_snapshot(q)
    return {
        "feature": "global",
        "plan": getattr(q, "plan", None) or "essentiel",
        "tokens_used": snap["used"],
        "tokens_limit": snap["limit"],
        "remaining": snap["remaining"],
    }


def _estimate_tokens(payload: MarketOpportunitiesIn) -> int:
    text = payload.model_dump_json(exclude_none=True)
    return max(2200, min(int(len(text) / 4) + 2600, 6500))


def _read_profile_context(db: Session, user_id: int) -> Dict[str, Any]:
    if read_profile is None:
        return {}
    try:
        profile = read_profile(db, user_id) or {}
        return profile if isinstance(profile, dict) else {}
    except Exception:
        return {}


def _build_ai_payload(payload: MarketOpportunitiesIn, db: Session, user_id: int) -> Dict[str, Any]:
    profile = _read_profile_context(db, user_id)
    business_model = payload.business_model or payload.businessModel or "offre_digitale"
    ctx = payload.context if isinstance(payload.context, dict) else {}

    return {
        "businessModel": business_model,
        "business_model": business_model,
        "parcours": payload.parcours or "creation_produit_digital",
        "objective": payload.objective or ctx.get("businessGoal") or "premiers_revenus",
        "level": payload.level or ctx.get("level") or "debutant",
        "audienceSize": payload.audienceSize or ctx.get("audienceSize") or "moins_500",
        "mainBlocker": payload.mainBlocker or ctx.get("mainBlocker") or "dispersion",
        "primaryChannel": payload.primaryChannel or ctx.get("primaryChannel") or "instagram",
        "count": payload.count or 5,
        "existingOffer": payload.existingOffer or ctx.get("existingOffer") or "",
        "prompt": payload.prompt or "",
        "context": {
            **ctx,
            "coach_profile": profile,
            "alex_business_project": profile.get("alex_business_project") or {},
        },
    }


def _fallback_opportunities() -> list[dict[str, Any]]:
    return [
        {
            "id": "fallback_reconversion_45_plus",
            "title": "Reconversion professionnelle 45+",
            "badge": "Fallback premium",
            "demand": "Demande forte et durable",
            "score": 94,
            "why": "Audience émotionnelle, besoin de sécurité, recherche d'un revenu complémentaire réaliste.",
            "product": "Formation courte + plan d'action 30 jours + templates",
            "price": "197€ à 497€",
            "offerDescription": "Un programme digital pour aider les salariés et personnes en transition de 45 ans et plus à construire une activité en ligne réaliste, sans repartir de zéro.",
            "problemSolved": "Aider des personnes expérimentées mais bloquées à transformer leur vécu ou leurs compétences en projet digital concret.",
            "transformationPromise": "Passer d'une inquiétude professionnelle à un plan clair pour créer une première offre digitale et préparer un revenu complémentaire.",
            "targetAudienceDescription": "Avatar : Sophie, 49 ans. Elle sent que son avenir professionnel est fragile, manque de temps et veut une méthode simple, rassurante et guidée.",
        },
        {
            "id": "fallback_ia_independants",
            "title": "IA pour indépendants",
            "badge": "Fallback premium",
            "demand": "Forte demande business",
            "score": 93,
            "why": "Les indépendants veulent gagner du temps, créer du contenu et mieux vendre sans complexité.",
            "product": "Mini-formation IA + prompts prêts à l'emploi",
            "price": "97€ à 297€",
            "offerDescription": "Une formation pratique pour aider les indépendants à utiliser l'IA afin de gagner du temps, créer du contenu et améliorer leur communication commerciale.",
            "problemSolved": "Aider les professionnels seuls ou débordés à utiliser l'IA concrètement, sans jargon.",
            "transformationPromise": "Passer d'un usage confus de l'IA à un système simple de prompts et d'actions commerciales utilisables chaque semaine.",
            "targetAudienceDescription": "Avatar : Julien, 38 ans. Indépendant compétent, débordé par la communication et la création de contenu.",
        },
        {
            "id": "fallback_marketing_digital_debutants",
            "title": "Marketing digital simplifié",
            "badge": "Fallback premium",
            "demand": "Audience massive",
            "score": 92,
            "why": "Les débutants sont noyés dans l'information et cherchent une méthode claire pour obtenir leurs premières ventes.",
            "product": "Méthode simple + calendrier de contenu + tunnel basique",
            "price": "97€ à 397€",
            "offerDescription": "Une méthode digitale simple pour aider les débutants à comprendre le marketing digital, choisir une offre et mettre en place un premier système de vente.",
            "problemSolved": "Aider les débutants à arrêter de consommer des formations dans tous les sens et à suivre une méthode claire.",
            "transformationPromise": "Passer d'un débutant perdu à une personne capable de publier, expliquer son offre et ouvrir ses premières conversations de vente.",
            "targetAudienceDescription": "Avatar : Laura, 34 ans. Elle veut gagner de l'argent en ligne mais ne sait pas quoi faire dans quel ordre.",
        },
        {
            "id": "fallback_faceless_ia",
            "title": "Contenu faceless avec IA",
            "badge": "Fallback premium",
            "demand": "Tendance créateur forte",
            "score": 91,
            "why": "Beaucoup veulent publier sans montrer leur visage tout en construisant une audience monétisable.",
            "product": "Méthode faceless + prompts + scripts reels",
            "price": "47€ à 197€",
            "offerDescription": "Une méthode digitale pour créer du contenu faceless avec l'IA, structurer des scripts courts et publier régulièrement sans se montrer.",
            "problemSolved": "Aider les personnes qui n'osent pas se montrer à publier du contenu utile et monétisable.",
            "transformationPromise": "Passer de la peur de s'exposer à une stratégie de contenu discrète, structurée et capable d'attirer une audience ciblée.",
            "targetAudienceDescription": "Avatar : Manon, 29 ans. Elle veut lancer un projet en ligne mais ne veut pas se filmer.",
        },
        {
            "id": "fallback_email_marketing",
            "title": "Email marketing simple",
            "badge": "Fallback premium",
            "demand": "Forte valeur business",
            "score": 90,
            "why": "L'email convertit, mais beaucoup ne savent pas quoi écrire ni quand relancer.",
            "product": "Séquences email prêtes à adapter + formation courte",
            "price": "97€ à 297€",
            "offerDescription": "Une formation courte pour aider les indépendants à créer une première séquence email simple, humaine et orientée vente.",
            "problemSolved": "Aider les indépendants à arrêter de dépendre uniquement des réseaux sociaux et à convertir grâce à des emails simples.",
            "transformationPromise": "Passer d'une audience dispersée à une séquence email claire qui nourrit la relation et mène naturellement vers la vente.",
            "targetAudienceDescription": "Avatar : Céline, 39 ans. Elle a une petite audience mais ne sait pas vendre par email.",
        },
    ]


def _normalize_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        opportunities = result.get("opportunities") or result.get("niches") or result.get("items") or []
        if isinstance(opportunities, list) and opportunities:
            return {**result, "success": True, "opportunities": opportunities[:5]}
    if isinstance(result, list) and result:
        return {"success": True, "source": "openai", "opportunities": result[:5]}
    return {"success": False, "source": "fallback_route", "opportunities": _fallback_opportunities()}


def _handle_market_opportunities(
    payload: MarketOpportunitiesIn,
    current_user: Any,
    db: Session,
) -> Dict[str, Any]:
    user_id = _user_id(current_user)

    q = get_or_create_quota(db, user_id, feature="global")
    snap = _quota_snapshot(q)
    if snap["limit"] > 0 and snap["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    reserved_tokens = _estimate_tokens(payload)
    reserved_quota = update_quota(db, user_id, reserved_tokens, feature="global")
    if reserved_quota is None:
        raise HTTPException(status_code=402, detail="Quota IA atteint")

    ai_payload = _build_ai_payload(payload, db, user_id)

    try:
        result = generate_market_opportunities(
            payload=ai_payload,
            user_id=user_id,
            user_email=_user_get(current_user, "email"),
            user_name=_user_get(current_user, "name") or _user_get(current_user, "full_name"),
            plan=getattr(q, "plan", None) or "essentiel",
        )
    except TypeError:
        result = generate_market_opportunities(ai_payload)
    except Exception as exc:
        return {
            "success": False,
            "source": "fallback_route_error",
            "error": str(exc),
            "tokens_consumed": reserved_tokens,
            "quota": _quota_response(reserved_quota),
            "opportunities": _fallback_opportunities(),
        }

    normalized = _normalize_result(result)
    normalized["tokens_consumed"] = reserved_tokens
    normalized["quota"] = _quota_response(reserved_quota)
    return normalized


@router.post("/coach/market-opportunities")
def coach_market_opportunities(
    payload: MarketOpportunitiesIn,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _handle_market_opportunities(payload, current_user, db)


@router.post("/market-opportunities")
def market_opportunities_alias(
    payload: MarketOpportunitiesIn,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _handle_market_opportunities(payload, current_user, db)
