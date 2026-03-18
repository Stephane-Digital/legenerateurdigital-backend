
from typing import Dict, Any

def compute_email_metrics(events: list) -> Dict[str, Any]:
    stats = {
        "contacts": 0,
        "campaign_starts": 0,
        "sales": 0
    }

    for e in events:
        if e.get("event") == "contact_created":
            stats["contacts"] += 1
        if e.get("event") == "campaign_started":
            stats["campaign_starts"] += 1
        if e.get("event") == "purchase":
            stats["sales"] += 1

    return stats
