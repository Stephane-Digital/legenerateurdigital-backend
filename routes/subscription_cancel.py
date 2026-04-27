from datetime import datetime
import html
import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/subscription", tags=["Subscription"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

# IMPORTANT LGD :
# On réutilise les variables déjà présentes en production Render.
# Le domaine est déjà validé puisque les emails d'activation token partent correctement.
FROM_EMAIL = os.getenv(
    "LGD_ACTIVATION_FROM_EMAIL",
    "Le Générateur Digital <no-reply@legenerateurdigital.com>",
).strip()

ADMIN_EMAIL = os.getenv(
    "LGD_SUPPORT_EMAIL",
    "contact@legenerateurdigital.com",
).strip()


def _get_user_value(user: Any, key: str, default: str = "") -> str:
    if isinstance(user, dict):
        value = user.get(key, default)
    else:
        value = getattr(user, key, default)

    if value is None:
        return default

    return str(value).strip()


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
            detail="RESEND_API_KEY manquant côté serveur Render.",
        )

    if not FROM_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="LGD_ACTIVATION_FROM_EMAIL manquant côté serveur Render.",
        )

    if not ADMIN_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="LGD_SUPPORT_EMAIL manquant côté serveur Render.",
        )

    safe_user_name = html.escape(user_name)
    safe_user_email = html.escape(user_email)
    safe_user_plan = html.escape(user_plan)
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    html_content = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;padding:20px;color:#111;line-height:1.6;">
      <h2 style="margin:0 0 16px;">Demande de résiliation LGD</h2>
      <p><strong>Nom :</strong> {safe_user_name}</p>
      <p><strong>Email :</strong> {safe_user_email}</p>
      <p><strong>Plan actuel :</strong> {safe_user_plan}</p>
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

    text_content = (
        "Demande de résiliation LGD\n\n"
        f"Nom : {user_name}\n"
        f"Email : {user_email}\n"
        f"Plan actuel : {user_plan}\n"
        f"Date de demande : {now}\n\n"
        "Action à effectuer : résilier manuellement l'abonnement correspondant dans Systeme.io."
    )

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
                "text": text_content,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur réseau Resend: {str(exc)}",
        )

    response_text = response.text or ""

    try:
        response_json = response.json()
    except ValueError:
        response_json = {}

    if response.status_code not in (200, 202):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Resend a refusé l'envoi de l'email de résiliation.",
                "resend_status": response.status_code,
                "resend_body": response_text,
                "from": FROM_EMAIL,
                "to": ADMIN_EMAIL,
            },
        )

    resend_id = response_json.get("id") if isinstance(response_json, dict) else None

    return {
        "success": True,
        "message": "Demande de résiliation envoyée à LGD.",
        "resend_status": response.status_code,
        "resend_id": resend_id,
        "from": FROM_EMAIL,
        "to": ADMIN_EMAIL,
    }
