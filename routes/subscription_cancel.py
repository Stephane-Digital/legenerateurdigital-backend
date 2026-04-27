from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

import requests
import os

router = APIRouter(prefix="/subscription", tags=["Subscription"])


RESEND_API_KEY = os.getenv("RESEND_API_KEY")
ADMIN_EMAIL = "contact@legenerateurdigital.com"


@router.post("/cancel-request")
def cancel_subscription_request(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        # 🔐 récupération user (compatible dict ou ORM)
        user_email = (
            current_user["email"] if isinstance(current_user, dict) else current_user.email
        )
        user_name = (
            current_user.get("name")
            if isinstance(current_user, dict)
            else getattr(current_user, "name", "Utilisateur")
        )
        user_plan = (
            current_user.get("plan")
            if isinstance(current_user, dict)
            else getattr(current_user, "plan", "inconnu")
        )

        # 📅 date demande
        now = datetime.utcnow().strftime("%d/%m/%Y %H:%M")

        # 📧 contenu email
        html_content = f"""
        <div style="font-family:Arial;padding:20px">
            <h2>Demande de résiliation LGD</h2>
            <p><strong>Nom :</strong> {user_name}</p>
            <p><strong>Email :</strong> {user_email}</p>
            <p><strong>Plan :</strong> {user_plan}</p>
            <p><strong>Date :</strong> {now}</p>
        </div>
        """

        # 🚀 appel Resend
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "LGD <no-reply@legenerateurdigital.com>",
                "to": [ADMIN_EMAIL],
                "subject": "🚨 Demande de résiliation abonnement LGD",
                "html": html_content,
            },
        )

       if response.status_code not in (200, 202):
    raise HTTPException(
        status_code=500,
        detail=f"Erreur Resend {response.status_code}: {response.text}",
    )

        return {"success": True, "message": "Demande envoyée"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
