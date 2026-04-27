from datetime import datetime
import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/subscription", tags=["Subscription"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
ADMIN_EMAIL = "contact@legenerateurdigital.com"
FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "LGD <no-reply@legenerateurdigital.com>")


def _get_user_value(user: Any, key: str, default: str = "") -> str:
    if isinstance(user, dict):
        value = user.get(key, default)
    else:
        value = getattr(user, key, default)

    if value is None:
        return default

    return str(value)


@router.post("/cancel-request")
def cancel_subscription_request(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    user_email = _get_user_value(current_user, "email", "")
    user_name = _get_user_value(current_user, "name", "Utilisateur LGD")
    user_plan = _get_user_value(current_user, "plan", "inconnu")

    if not user_email:
        raise HTTPException(
            status_code=400,
            detail="Impossible de récupérer l'adresse email de l'utilisateur connecté.",
        )

    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="RESEND_API_KEY manquant côté serveur.",
        )

    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    html_content = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;padding:20px;color:#111;">
      <h2 style="margin:0 0 16px;">Demande de résiliation LGD</h2>
      <p><strong>Nom :</strong> {user_name}</p>
      <p><strong>Email :</strong> {user_email}</p>
      <p><strong>Plan actuel :</strong> {user_plan}</p>
      <p><strong>Date de demande :</strong> {now}</p>
      <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;" />
      <p>
        Cette demande a été envoyée automatiquement depuis le bouton
        “Se désabonner” du dashboard LGD.
      </p>
      <p>
        Action à effectuer : résilier manuellement l'abonnement correspondant dans Systeme.io.
      </p>
    </div>
    """

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [ADMIN_EMAIL],
                "reply_to": user_email,
                "subject": "Demande de résiliation abonnement LGD",
                "html": html_content,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur réseau Resend: {str(exc)}",
        )

    if response.status_code not in (200, 202):
        raise HTTPException(
            status_code=500,
            detail=f"Erreur Resend {response.status_code}: {response.text}",
        )

    return {
        "success": True,
        "message": "Demande de résiliation envoyée.",
    }
