
from typing import Dict, Any
from datetime import datetime

from services.integrations.systeme_io_client import SystemeIOClient
from services.logs.systeme_log_service import log_systeme_event


def dispatch_email_campaign(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envoie un payload Emailing IA vers Systeme.io
    - crée le contact
    - applique les tags
    - journalise l'action côté LGD
    """

    client = SystemeIOClient()

    campaign = payload.get("campaign", {})
    tags = campaign.get("tags", [])

    email = payload.get("contact_email")
    first_name = payload.get("first_name", "")
    last_name = payload.get("last_name", "")

    if not email:
        raise ValueError("contact_email manquant dans le payload")

    contact = client.create_contact(
        email=email,
        first_name=first_name,
        last_name=last_name,
        tags=tags,
    )

    log_systeme_event({
        "event": "systeme_contact_created",
        "email": email,
        "tags": tags,
        "campaign": campaign.get("name"),
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "status": "sent",
        "contact": contact,
        "tags_applied": tags
    }
