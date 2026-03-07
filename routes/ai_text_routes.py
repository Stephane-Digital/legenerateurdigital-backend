from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import get_current_user
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
    """
    Réécrit un texte avec un ton optionnel.
    Utilise services.content_engine_service.rewrite_text

    ⚠️ FIX LGD:
    - La fonction rewrite_text() du service accepte un texte (et options tone/max_length),
      mais ne prend pas original_text/user_id/db.
    - On conserve l'auth pour sécuriser l'endpoint, sans casser l'existant.
    """

    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide.")

    # db et user sont gardés volontairement (auth + future logging),
    # mais non nécessaires pour la réécriture en V1.
    result = rewrite_text(
        text=payload.text,
        tone=payload.tone,
        max_length=payload.max_length,
    )

    return {"result": result}
