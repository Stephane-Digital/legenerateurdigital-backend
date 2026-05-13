from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.lead_engine_memory_model import LeadEngineMemory
from routes.auth import get_current_user
from schemas.lead_engine_memory import LeadGenerateRequest, LeadMemoryCreate
from services.ai.lead_engine_ai import generate_lead_content
from services.ai_quota_service import get_or_create_quota, update_quota

router = APIRouter(prefix="/lead-engine/ai", tags=["Lead Engine AI"])


DEFAULT_LANDING_OUTPUT_CHARS = 8200
MAX_LANDING_OUTPUT_CHARS = 12000


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _serialize_memory(row: LeadEngineMemory) -> dict:
    return {
        "id": int(row.id),
        "user_id": int(row.user_id),
        "memory_type": str(row.memory_type),
        "goal": row.goal,
        "content": row.content,
        "emotional_profile": row.emotional_profile,
        "business_context": row.business_context,
        "metadata_json": row.metadata_json,
        "created_at": str(row.created_at) if row.created_at else None,
    }


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


def _quota_snapshot(q: Any) -> Dict[str, int | str]:
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

    return {
        "feature": "global",
        "plan": getattr(q, "plan", None) or "essentiel",
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
    }


def _estimate_tokens(*parts: str) -> int:
    text = " ".join([str(p or "") for p in parts])
    return max(1, int(len(text) / 4))


def _safe_max_length(value: Any, goal: Any = None, page_type: Any = None) -> int:
    """
    Correctif PROD V10.6 : l'ancien clamp 400–3000 était la cause principale
    des sorties OpenAI trop courtes à 1 ou 2 blocs. Pour landing_complete,
    on impose une vraie fenêtre de sortie backend.
    """
    n = _to_int(value, 0)
    raw_goal = str(goal or "").strip().lower()
    raw_page_type = str(page_type or "").strip().lower()

    is_landing = raw_goal == "landing_complete" or raw_page_type in {"lead_magnet", "landing", "landing_complete"}

    if is_landing:
        if n < 6500:
            return DEFAULT_LANDING_OUTPUT_CHARS
        return max(6500, min(n, MAX_LANDING_OUTPUT_CHARS))

    if n <= 0:
        n = 1800
    return max(400, min(n, 5000))


@router.post("/save-memory")
def save_memory(
    payload: LeadMemoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    memory = LeadEngineMemory(
        user_id=_user_id(current_user),
        memory_type=(payload.memory_type or "brief").strip()[:80],
        goal=(payload.goal or None),
        content=payload.content.strip(),
        emotional_profile=payload.emotional_profile,
        business_context=payload.business_context,
        metadata_json=payload.metadata_json,
    )

    db.add(memory)
    db.commit()
    db.refresh(memory)

    return {"status": "saved", "item": _serialize_memory(memory)}


@router.get("/memory")
def get_memory(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = 50,
):
    safe_limit = max(1, min(int(limit or 50), 200))
    rows = (
        db.query(LeadEngineMemory)
        .filter(LeadEngineMemory.user_id == _user_id(current_user))
        .order_by(LeadEngineMemory.created_at.desc(), LeadEngineMemory.id.desc())
        .limit(safe_limit)
        .all()
    )
    return [_serialize_memory(row) for row in rows]


@router.post("/generate")
def generate(
    payload: LeadGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = _user_id(current_user)

    quota = get_or_create_quota(db, user_id, feature="global")
    snap = _quota_snapshot(quota)
    if _to_int(snap["tokens_limit"], 0) > 0 and _to_int(snap["remaining"], 0) <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Quota IA atteint pour le moment.",
                "quota": snap,
            },
        )

    max_length = _safe_max_length(payload.max_length, payload.goal, payload.page_type)

    # Estimation réaliste : on tient compte du brief + de la sortie demandée.
    # Ce n'est pas la facture OpenAI réelle, mais cela évite de sous-décrémenter fortement le quota LGD.
    estimated_tokens = max(
        420,
        min(
            _estimate_tokens(
                payload.goal,
                payload.brief,
                payload.emotional_style or "",
                payload.business_context or "",
                payload.objective or "",
                payload.angle or "",
                payload.audience or "",
                payload.tone or "",
                payload.page_type or "",
            )
            + int(max_length / 3.2)
            + 260,
            4200,
        ),
    )

    memories = (
        db.query(LeadEngineMemory)
        .filter(LeadEngineMemory.user_id == user_id)
        .order_by(LeadEngineMemory.created_at.desc(), LeadEngineMemory.id.desc())
        .limit(1)
        .all()
    )
    serialized_memories = [] if payload.goal == "rewrite_landing" else [_serialize_memory(row) for row in memories]

    try:
        content = generate_lead_content(
            goal=payload.goal,
            brief=payload.brief,
            emotional_style=payload.emotional_style,
            business_context=payload.business_context,
            memories=serialized_memories,
            objective=payload.objective,
            angle=payload.angle,
            audience=payload.audience,
            tone=payload.tone,
            max_length=max_length,
            cta_url=payload.cta_url,
            page_type=payload.page_type,
        )
    except Exception as exc:
        # 502 = OpenAI / génération distante invalide, pas une erreur frontend.
        raise HTTPException(status_code=502, detail=f"LEAD_ENGINE_AI_ERROR: {exc}") from exc

    updated_quota = update_quota(db, user_id, estimated_tokens, feature="global")
    if updated_quota is None:
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Quota IA atteint pour le moment.",
                "quota": _quota_snapshot(get_or_create_quota(db, user_id, feature="global")),
            },
        )

    memory = LeadEngineMemory(
        user_id=user_id,
        memory_type="generation",
        goal=payload.goal,
        content=content,
        emotional_profile=payload.emotional_style,
        business_context=" | ".join(
            part
            for part in [
                payload.business_context,
                f"objective={payload.objective}" if payload.objective else "",
                f"angle={payload.angle}" if payload.angle else "",
                f"audience={payload.audience}" if payload.audience else "",
                f"tone={payload.tone}" if payload.tone else "",
                f"page_type={payload.page_type}" if payload.page_type else "",
                f"max_length={max_length}" if max_length else "",
            ]
            if str(part or "").strip()
        ),
    )
    db.add(memory)
    db.commit()

    return {
        "content": content,
        "memory_items_used": len(serialized_memories),
        "tokens_consumed": estimated_tokens,
        "quota": _quota_snapshot(updated_quota),
    }

