from datetime import datetime
import html
import os
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/subscription", tags=["Subscription"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

# On réutilise les variables déjà présentes en production Render.
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


def _send_resend_email(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    reply_to: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }

    if reply_to:
        payload["reply_to"] = reply_to

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
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
                "message": "Resend a refusé l'envoi de l'email.",
                "resend_status": response.status_code,
                "resend_body": response_text,
                "from": FROM_EMAIL,
                "to": to_email,
            },
        )

    return {
        "status": response.status_code,
        "id": response_json.get("id") if isinstance(response_json, dict) else None,
        "to": to_email,
    }


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

    admin_html = f"""
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

    admin_text = (
        "Demande de résiliation LGD\n\n"
        f"Nom : {user_name}\n"
        f"Email : {user_email}\n"
        f"Plan actuel : {user_plan}\n"
        f"Date de demande : {now}\n\n"
        "Action à effectuer : résilier manuellement l'abonnement correspondant dans Systeme.io."
    )

    user_html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;padding:20px;color:#111;line-height:1.6;">
      <h2 style="margin:0 0 16px;">Votre demande de résiliation a bien été reçue</h2>
      <p>Bonjour {safe_user_name},</p>
      <p>
        Nous confirmons la bonne réception de votre demande de résiliation pour votre abonnement
        <strong>Le Générateur Digital</strong>.
      </p>
      <p><strong>Email du compte :</strong> {safe_user_email}</p>
      <p><strong>Plan actuel :</strong> {safe_user_plan}</p>
      <p><strong>Date de demande :</strong> {now}</p>
      <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;" />
      <p>
        Votre demande sera traitée manuellement dans les meilleurs délais.
        Votre accès reste actif jusqu'au traitement effectif de la résiliation ou jusqu'à la fin de la période déjà réglée,
        selon les conditions applicables.
      </p>
      <p>
        Pour toute question, vous pouvez répondre directement à cet email.
      </p>
      <p style="margin-top:24px;">
        L'équipe Le Générateur Digital
      </p>
    </div>
    """

    user_text = (
        "Votre demande de résiliation a bien été reçue\n\n"
        f"Bonjour {user_name},\n\n"
        "Nous confirmons la bonne réception de votre demande de résiliation pour votre abonnement Le Générateur Digital.\n\n"
        f"Email du compte : {user_email}\n"
        f"Plan actuel : {user_plan}\n"
        f"Date de demande : {now}\n\n"
        "Votre demande sera traitée manuellement dans les meilleurs délais. "
        "Votre accès reste actif jusqu'au traitement effectif de la résiliation ou jusqu'à la fin de la période déjà réglée, "
        "selon les conditions applicables.\n\n"
        "Pour toute question, vous pouvez répondre directement à cet email.\n\n"
        "L'équipe Le Générateur Digital"
    )

    admin_result = _send_resend_email(
        to_email=ADMIN_EMAIL,
        reply_to=user_email,
        subject="Demande de résiliation abonnement LGD",
        html_content=admin_html,
        text_content=admin_text,
    )

    user_result = _send_resend_email(
        to_email=user_email,
        reply_to=ADMIN_EMAIL,
        subject="Confirmation de votre demande de résiliation LGD",
        html_content=user_html,
        text_content=user_text,
    )

    return {
        "success": True,
        "message": "Demande de résiliation envoyée à LGD et confirmation envoyée à l'utilisateur.",
        "admin_email": {
            "resend_status": admin_result["status"],
            "resend_id": admin_result["id"],
            "to": admin_result["to"],
        },
        "user_email": {
            "resend_status": user_result["status"],
            "resend_id": user_result["id"],
            "to": user_result["to"],
        },
        "from": FROM_EMAIL,
    }

