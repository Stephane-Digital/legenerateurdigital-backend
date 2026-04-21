from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from database import get_db
from models.user_model import User
from services.auth_service import hash_password

router = APIRouter(prefix="/auth", tags=["Auth Reset"])


# ============================
# 📩 REQUEST RESET
# ============================
class ResetRequest(BaseModel):
    email: str


@router.post("/forgot-password")
def forgot_password(payload: ResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        return {"ok": True}  # sécurité (pas révéler email)

    token = str(uuid.uuid4())

    user.password_reset_token = token
    user.password_reset_expires = datetime.utcnow() + timedelta(minutes=15)

    db.commit()

FRONT_URL = "https://legenerateurdigital-front.vercel.app"

print(f"🔗 RESET LINK: {FRONT_URL}/auth/reset-password?token={token}")

    return {"ok": True}


# ============================
# 🔐 RESET PASSWORD
# ============================
class ResetConfirm(BaseModel):
    token: str
    password: str


@router.post("/reset-password")
def reset_password(payload: ResetConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.password_reset_token == payload.token
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Token invalide")

    if user.password_reset_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expiré")

    user.hashed_password = hash_password(payload.password)
    user.password_reset_token = None
    user.password_reset_expires = None

    db.commit()

    return {"ok": True}
