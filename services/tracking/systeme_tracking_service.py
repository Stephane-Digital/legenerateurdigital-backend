
from datetime import datetime
from typing import Dict, Any

def handle_systeme_event(payload: Dict[str, Any]):
    event_type = payload.get("event")

    log = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "data": payload
    }

    print("[LGD WEBHOOK EVENT]", log)

    if event_type == "contact_tagged":
        return {"status": "tag_received"}

    if event_type == "campaign_started":
        return {"status": "campaign_started_logged"}

    if event_type == "purchase":
        return {"status": "sale_tracked"}

    return {"status": "event_received"}
