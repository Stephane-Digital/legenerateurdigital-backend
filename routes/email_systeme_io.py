
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from services.integrations.systeme_io_client import SystemeIOClient

router = APIRouter()


@router.post("/email-campaigns/{campaign_id}/send-systeme-io")
def send_campaign_to_systeme_io(campaign_id: int, payload: Dict[str, Any]):
    """
    Route LGD pour envoyer une campagne Emailing IA vers Systeme.io
    Cette route ne casse rien dans l'existant et utilise simplement
    le client Systeme.io pour créer un contact et appliquer les tags.
    """

    try:
        client = SystemeIOClient()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        campaign = payload.get("campaign", {})
        tags = campaign.get("tags", [])

        contact_email = payload.get("contact_email")
        first_name = payload.get("first_name", "")
        last_name = payload.get("last_name", "")

        if not contact_email:
            raise HTTPException(status_code=400, detail="contact_email manquant")

        # Création du contact
        contact = client.create_contact(
            email=contact_email,
            first_name=first_name,
            last_name=last_name,
            tags=tags
        )

        return {
            "status": "success",
            "campaign_id": campaign_id,
            "contact_created": True,
            "systeme_response": contact
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Systeme.io: {str(e)}")
