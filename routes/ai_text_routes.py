from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.content_engine_service import rewrite_text

router = APIRouter(prefix="/ai/text", tags=["AI Text"])


# ============================================================
# 📌 PAYLOAD
# ============================================================

class RewritePayload(BaseModel):
    text: str
    tone: Optional[str] = None
    max_length: Optional[int] = None


# ============================================================
# 🧠 RÉÉCRITURE TEXTE
# ============================================================

@router.post("/rewrite")
def ai_rewrite_text(
    payload: RewritePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide.")

    result = rewrite_text(
        text=payload.text,
        tone=payload.tone,
        max_length=payload.max_length,
    )

    return {"result": result}
