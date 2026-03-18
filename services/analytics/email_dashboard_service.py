
from typing import Dict

# ⚠️ Version simple basée sur mémoire (remplaçable plus tard par DB)
_events = []


def register_event(event: dict):
    _events.append(event)


def get_dashboard_stats() -> Dict:
    stats = {
        "contacts_captured": 0,
        "campaigns_started": 0,
        "sales_generated": 0,
    }

    for e in _events:
        if e.get("event") == "contact_created":
            stats["contacts_captured"] += 1

        if e.get("event") == "campaign_started":
            stats["campaigns_started"] += 1

        if e.get("event") == "purchase":
            stats["sales_generated"] += 1

    return {
        "module": "LGD Emailing IA",
        "stats": stats,
        "events_tracked": len(_events),
    }
