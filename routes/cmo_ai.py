from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.cmo_ai import generate_cmo_strategy
from services.ai_quota_service import update_quota

router = APIRouter(prefix="/cmo-ai", tags=["CMO IA V5"])


class CmoStrategyRequest(BaseModel):
    objective: str

    # Champs historiques déjà utilisés par le backend CMO V5
    niche: Optional[str] = None
    audience: Optional[str] = None
    offer: Optional[str] = None
    current_situation: Optional[str] = None
    constraints: Optional[str] = None
    preferred_channel: Optional[str] = None
    tone: Optional[str] = "premium, humain, direct"
    user_level: Optional[str] = "intermediate"

    # Compatibilité CMO V2 frontend
    blocker: Optional[str] = None
    module: Optional[str] = None


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _estimate_tokens(payload: CmoStrategyRequest) -> int:
    text = " ".join(
        [
            str(payload.objective or ""),
            str(payload.niche or ""),
            str(payload.audience or ""),
            str(payload.offer or ""),
            str(payload.current_situation or ""),
            str(payload.constraints or ""),
            str(payload.preferred_channel or ""),
            str(payload.tone or ""),
            str(payload.user_level or ""),
            str(payload.blocker or ""),
            str(payload.module or ""),
        ]
    )
    return max(1800, min(int(len(text) / 3) + 2200, 15000))


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _extract_strategy(result: Any, payload: CmoStrategyRequest) -> Dict[str, str]:
    """
    Normalise la réponse IA pour le frontend CMO V2.

    Le service generate_cmo_strategy peut renvoyer :
    - directement un dict stratégique,
    - un dict contenant strategy/result/content,
    - ou du texte.

    Cette fonction garantit toujours les clés attendues côté frontend :
    target, pain, desire, promise, angle, mechanism, cta.
    """
    objective = _safe_text(payload.objective, "Créer une action marketing utile.")
    blocker = _safe_text(payload.blocker or payload.current_situation or payload.constraints)
    offer = _safe_text(payload.offer, "l’offre")
    audience = _safe_text(payload.audience, "audience cible")

    fallback = {
        "target": audience,
        "pain": blocker or "Le message et l’action doivent être clarifiés.",
        "desire": "Obtenir une action marketing claire, utile et exploitable.",
        "promise": f"Transformer {offer} en message clair et désirable.",
        "angle": f"Présenter {offer} sans pression, avec une valeur claire.",
        "mechanism": "Diagnostic simple, angle stratégique, message concret et CTA actionnable.",
        "cta": f"Découvrir {offer}" if offer != "l’offre" else "Passer à l’action",
    }

    raw: Any = result

    if isinstance(raw, dict):
        if isinstance(raw.get("strategy"), dict):
            raw = raw.get("strategy")
        elif isinstance(raw.get("result"), dict):
            raw = raw.get("result")
        elif isinstance(raw.get("content"), dict):
            raw = raw.get("content")

    if isinstance(raw, dict):
        return {
            "target": _safe_text(raw.get("target"), fallback["target"]),
            "pain": _safe_text(raw.get("pain"), fallback["pain"]),
            "desire": _safe_text(raw.get("desire"), fallback["desire"]),
            "promise": _safe_text(raw.get("promise"), fallback["promise"]),
            "angle": _safe_text(raw.get("angle"), fallback["angle"]),
            "mechanism": _safe_text(raw.get("mechanism"), fallback["mechanism"]),
            "cta": _safe_text(raw.get("cta"), fallback["cta"]),
        }

    # Si l'IA renvoie du texte libre, on ne casse pas le front.
    # Le texte est conservé dans "angle" et le fallback complète le reste.
    if isinstance(raw, str) and raw.strip():
        fallback["angle"] = raw.strip()[:800]

    return fallback


@router.post("/strategy")
def cmo_strategy(
    payload: CmoStrategyRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    uid = _user_id(current_user)
    amount = _estimate_tokens(payload)

    quota = update_quota(db, uid, amount, feature="coach")
    if quota is None:
        raise HTTPException(status_code=400, detail="Quota IA insuffisant.")

    current_situation = payload.current_situation or payload.blocker or ""
    constraints = payload.constraints or payload.blocker or ""

    try:
        result = generate_cmo_strategy(
            objective=payload.objective,
            niche=payload.niche or "",
            audience=payload.audience or "",
            offer=payload.offer or "",
            current_situation=current_situation,
            constraints=constraints,
            preferred_channel=payload.preferred_channel or payload.module or "",
            tone=payload.tone or "premium, humain, direct",
            user_level=payload.user_level or "intermediate",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    strategy = _extract_strategy(result, payload)

    return {
        "success": True,
        "tokens_charged": amount,
        "strategy": strategy,
        "result": result,
    }


@router.get("/health")
def cmo_health():
    return {
        "status": "ok",
        "module": "CMO IA V5",
        "mode": "next_best_action",
    }
