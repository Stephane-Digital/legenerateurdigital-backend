import os
import uuid
from datetime import datetime, timedelta

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.user_model import User
from services.auth_service import hash_password

router = APIRouter(prefix="/auth", tags=["Auth Reset"])

resend.api_key = os.getenv("RESEND_API_KEY", "")

FRONT_URL = os.getenv(
    "LGD_FRONT_URL",
    "https://legenerateurdigital-front.vercel.app",
)


# ============================
# 📩 REQUEST RESET
# ============================
class ResetRequest(BaseModel):
    email: str


@router.post("/forgot-password")
def forgot_password(payload: ResetRequest, db: Session = Depends(get_db)):
    print("🔥 FORGOT PASSWORD TRIGGERED")
    print("📧 EMAIL DEMANDE:", payload.email)
    print("🌐 FRONT_URL:", FRONT_URL)
    print("🔑 RESEND KEY PRESENT:", bool(resend.api_key))

    user = db.query(User).filter(User.email == payload.email).first()

    # sécurité : on ne révèle jamais si l'email existe ou non
    if not user:
        print("⚠️ USER NOT FOUND FOR RESET")
        return {"ok": True}

    print("✅ USER FOUND:", user.email)

    token = str(uuid.uuid4())

    user.password_reset_token = token
    user.password_reset_expires = datetime.utcnow() + timedelta(minutes=15)

    db.commit()

    reset_link = f"{FRONT_URL}/auth/reset-password?token={token}"

    print(f"🔗 RESET LINK: {reset_link}")

    if resend.api_key:
        try:
            result = resend.Emails.send(
                {
                    "from": "LGD <contact@legenerateurdigital.com>",
                    "to": [user.email],
                    "subject": "Réinitialisation de votre mot de passe LGD",
                    "html": f"""
                    <div style="font-family:Arial,Helvetica,sans-serif;padding:24px;background:#0A0A0A;color:#FFFFFF">
                      <div style="max-width:560px;margin:0 auto;background:#111111;border:1px solid rgba(212,175,55,0.25);border-radius:16px;padding:32px">
                        <h1 style="margin:0 0 16px 0;color:#F5E7BE;font-size:24px;">Réinitialisation du mot de passe</h1>
                        <p style="margin:0 0 16px 0;color:#D6D6D6;">
                          Vous avez demandé la réinitialisation de votre mot de passe LGD.
                        </p>
                        <p style="margin:0 0 24px 0;color:#D6D6D6;">
                          Cliquez sur le bouton ci-dessous pour définir un nouveau mot de passe.
                        </p>
                        <a href="{reset_link}"
                           style="display:inline-block;padding:14px 22px;border-radius:10px;background:#D4AF37;color:#000000;text-decoration:none;font-weight:700;">
                          Réinitialiser mon mot de passe
                        </a>
                        <p style="margin:24px 0 0 0;color:#AFAFAF;font-size:14px;">
                          Ce lien expire dans 15 minutes.
                        </p>
                      </div>
                    </div>
                    """,
                }
            )
            print("✅ RESEND SENT:", result)
        except Exception as e:
            print("❌ RESEND ERROR:", repr(e))
    else:
        print("❌ RESEND SKIPPED: RESEND_API_KEY manquante ou vide")

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

    if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expiré")

    user.hashed_password = hash_password(payload.password)
    user.password_reset_token = None
    user.password_reset_expires = None

    db.commit()

    return {
        "ok": True,
        "email": user.email,
    }
