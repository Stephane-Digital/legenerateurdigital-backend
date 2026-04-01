from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.lead_engine_memory_model import LeadEngineMemory
from routes.auth import get_current_user
from schemas.lead_engine_memory import LeadGenerateRequest, LeadMemoryCreate
from services.ai.lead_engine_ai import generate_lead_content

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
    except Exception as exc:
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
    }
