from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from core.security import get_current_user
from models.user_model import User
from models.lead_engine_memory_model import LeadEngineMemory
from schemas.lead_engine_memory import LeadMemoryCreate, LeadGenerateRequest
from services.ai.lead_engine_ai import generate_lead_content

router = APIRouter(prefix="/lead-engine/ai", tags=["Lead Engine AI"])


@router.post("/save-memory")
def save_memory(
    payload: LeadMemoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = LeadEngineMemory(
        user_id=current_user.id,
        memory_type=payload.memory_type,
        content=payload.content,
        emotional_profile=payload.emotional_profile,
        business_context=payload.business_context,
    )

    db.add(memory)
    db.commit()
    db.refresh(memory)

    return {"status": "saved", "id": memory.id}


@router.get("/memory")
def get_memory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(LeadEngineMemory)
        .filter(LeadEngineMemory.user_id == current_user.id)
        .order_by(LeadEngineMemory.created_at.desc())
        .limit(50)
        .all()
    )

    return rows


@router.post("/generate")
def generate(
    payload: LeadGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = generate_lead_content(
        payload.goal,
        payload.brief,
        payload.emotional_style,
        payload.business_context,
    )

    memory = LeadEngineMemory(
        user_id=current_user.id,
        memory_type="generation",
        content=result,
        emotional_profile=payload.emotional_style,
        business_context=payload.business_context,
    )

    db.add(memory)
    db.commit()

    return {"content": result}
