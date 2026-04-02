
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.lead_engine_memory_model import LeadEngineMemory
from routes.auth import get_current_user
from schemas.lead_engine_memory import LeadGenerateRequest, LeadMemoryCreate
from services.ai.lead_engine_ai import generate_lead_content

try:
    from models.ia_quota_model import IAQuota  # type: ignore
except Exception:  # pragma: no cover
    IAQuota = None  # type: ignore

router = APIRouter(prefix="/lead-engine/ai", tags=["Lead Engine AI"])


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _quota_attr(row: Any, *names: str) -> Optional[str]:
    for name in names:
        if hasattr(row, name):
            return name
    return None


def _find_or_create_quota_row(db: Session, user_id: int, feature: str = "coach"):
    if IAQuota is None:
        return None

    query = db.query(IAQuota)
    if hasattr(IAQuota, "user_id"):
        query = query.filter(IAQuota.user_id == user_id)
    if hasattr(IAQuota, "feature"):
        query = query.filter(IAQuota.feature == feature)

    row = query.first()
    if row is not None:
        return row

    try:
        row = IAQuota()  # type: ignore[call-arg]
        if hasattr(row, "user_id"):
            setattr(row, "user_id", user_id)
        if hasattr(row, "feature"):
            setattr(row, "feature", feature)
        if hasattr(row, "used_tokens"):
            setattr(row, "used_tokens", 0)
        if hasattr(row, "limit_tokens"):
            # align with current coach quota defaults observed in admin UI
            setattr(row, "limit_tokens", 400000)
        db.add(row)
        db.flush()
        return row
    except Exception:
        db.rollback()
        return None


def _serialize_quota(row: Any) -> Optional[dict]:
    if row is None:
        return None

    used_attr = _quota_attr(row, "used_tokens", "used", "tokens_used")
    limit_attr = _quota_attr(row, "limit_tokens", "daily_limit", "limit")
    feature_attr = _quota_attr(row, "feature")
    plan_attr = _quota_attr(row, "plan")

    used = _safe_int(getattr(row, used_attr), 0) if used_attr else 0
    limit_value = _safe_int(getattr(row, limit_attr), 0) if limit_attr else 0
    remaining = max(0, limit_value - used)

    return {
        "feature": getattr(row, feature_attr) if feature_attr else "coach",
        "plan": getattr(row, plan_attr) if plan_attr else None,
        "used_tokens": used,
        "limit_tokens": limit_value,
        "remaining_tokens": remaining,
    }


def _consume_quota_or_raise(db: Session, user_id: int, tokens_to_consume: int, feature: str = "coach") -> dict:
    row = _find_or_create_quota_row(db, user_id, feature=feature)
    if row is None:
        return {
            "feature": feature,
            "used_tokens": 0,
            "limit_tokens": 0,
            "remaining_tokens": 0,
            "quota_enabled": False,
        }

    used_attr = _quota_attr(row, "used_tokens", "used", "tokens_used")
    limit_attr = _quota_attr(row, "limit_tokens", "daily_limit", "limit")
    if not used_attr or not limit_attr:
        return {
            "feature": feature,
            "used_tokens": 0,
            "limit_tokens": 0,
            "remaining_tokens": 0,
            "quota_enabled": False,
        }

    current_used = _safe_int(getattr(row, used_attr), 0)
    current_limit = _safe_int(getattr(row, limit_attr), 0)

    if current_limit > 0 and current_used + tokens_to_consume > current_limit:
        remaining = max(0, current_limit - current_used)
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Quota IA atteint pour Lead Engine.",
                "feature": feature,
                "used_tokens": current_used,
                "limit_tokens": current_limit,
                "remaining_tokens": remaining,
            },
        )

    setattr(row, used_attr, current_used + tokens_to_consume)
    db.flush()

    next_used = _safe_int(getattr(row, used_attr), 0)
    next_limit = _safe_int(getattr(row, limit_attr), 0)
    return {
        "feature": feature,
        "used_tokens": next_used,
        "limit_tokens": next_limit,
        "remaining_tokens": max(0, next_limit - next_used),
        "quota_enabled": True,
    }


def _estimate_token_cost(payload: LeadGenerateRequest, content: str) -> int:
    brief_cost = max(1, len(str(payload.brief or "").strip()) // 4)
    output_cost = max(1, len(str(content or "").strip()) // 4)
    context_cost = max(0, len(str(payload.business_context or "").strip()) // 8)
    style_cost = max(0, len(str(payload.emotional_style or "").strip()) // 8)
    return max(50, brief_cost + output_cost + context_cost + style_cost)


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

    memories = (
        db.query(LeadEngineMemory)
        .filter(LeadEngineMemory.user_id == user_id)
        .order_by(LeadEngineMemory.created_at.desc(), LeadEngineMemory.id.desc())
        .limit(20)
        .all()
    )
    serialized_memories = [_serialize_memory(row) for row in memories]

    try:
        content = generate_lead_content(
            goal=payload.goal,
            brief=payload.brief,
            emotional_style=payload.emotional_style,
            business_context=payload.business_context,
            memories=serialized_memories,
        )
        consumed = _estimate_token_cost(payload, content)
        quota = _consume_quota_or_raise(db, user_id=user_id, tokens_to_consume=consumed, feature="coach")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"LEAD_ENGINE_AI_ERROR: {exc}") from exc

    memory = LeadEngineMemory(
        user_id=user_id,
        memory_type="generation",
        goal=payload.goal,
        content=content,
        emotional_profile=payload.emotional_style,
        business_context=payload.business_context,
    )
    db.add(memory)
    db.commit()

    return {
        "content": content,
        "memory_items_used": len(serialized_memories),
        "quota": quota,
        "tokens_consumed": consumed,
    }
