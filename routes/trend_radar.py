from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai.trend_radar_ai import analyze_and_transform_trend
from services.ai_quota_service import update_quota

router = APIRouter(prefix="/trend-radar", tags=["Trend Radar V4"])


class TrendRadarRequest(BaseModel):
    source_text: Optional[str] = None
    source_url: Optional[str] = None
    niche: Optional[str] = None
    audience: Optional[str] = None
    offer: Optional[str] = None
    objective: Optional[str] = None
    output_type: Optional[str] = "post"
    tone: Optional[str] = "premium, humain, direct"


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _estimate_tokens(payload: TrendRadarRequest) -> int:
    text = " ".join(
        [
            str(payload.source_text or ""),
            str(payload.source_url or ""),
            str(payload.niche or ""),
            str(payload.audience or ""),
            str(payload.offer or ""),
            str(payload.objective or ""),
            str(payload.output_type or ""),
            str(payload.tone or ""),
        ]
    )
    return max(1200, min(int(len(text) / 3) + 1800, 12000))


@router.post("/analyze")
def analyze_trend_radar(
    payload: TrendRadarRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    if not (payload.source_text or payload.source_url):
        raise HTTPException(
            status_code=400,
            detail="Ajoute au moins un texte, une idée ou une URL à analyser.",
        )

    uid = _user_id(current_user)
    amount = _estimate_tokens(payload)

    quota = update_quota(db, uid, amount, feature="coach")
    if quota is None:
        raise HTTPException(status_code=400, detail="Quota IA insuffisant.")

    try:
        result = analyze_and_transform_trend(
            source_text=payload.source_text or "",
            source_url=payload.source_url,
            niche=payload.niche or "",
            audience=payload.audience or "",
            offer=payload.offer or "",
            objective=payload.objective or "",
            output_type=payload.output_type or "post",
            tone=payload.tone or "premium, humain, direct",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "success": True,
        "tokens_charged": amount,
        "result": result,
    }


@router.get("/health")
def trend_radar_health():
    return {
        "status": "ok",
        "module": "Trend Radar V4",
        "mode": "analysis_transform_no_copy",
    }
