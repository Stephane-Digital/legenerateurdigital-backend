import os
import requests
from typing import Dict, Any

MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")
MAKE_SHARED_SECRET = os.getenv("MAKE_SHARED_SECRET", "")


def build_make_payload(post: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "secret": MAKE_SHARED_SECRET,
        "post_id": post.get("id"),
        "network": post.get("network"),
        "content": post.get("content"),
        "media": post.get("media"),
        "scheduled_at": post.get("scheduled_at"),
    }


def send_to_make(post: Dict[str, Any]) -> Dict[str, Any]:
    if not MAKE_WEBHOOK_URL:
        raise ValueError("MAKE_WEBHOOK_URL manquant")

    payload = build_make_payload(post)

    response = requests.post(
        MAKE_WEBHOOK_URL,
        json=payload,
        timeout=15
    )

    response.raise_for_status()

    return response.json()
