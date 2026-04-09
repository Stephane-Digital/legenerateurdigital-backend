from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "").strip()
MAKE_SHARED_SECRET = os.getenv("MAKE_SHARED_SECRET", "").strip()

SUPPORTED_NETWORKS = {"instagram", "facebook", "linkedin", "pinterest", "snapchat"}
FINAL_STATUSES = {"published", "failed"}


def normalize_network(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in {"ig", "instagram"}:
        return "instagram"
    if v in {"fb", "facebook"}:
        return "facebook"
    if v in {"li", "linkedin", "linked_in"}:
        return "linkedin"
    if v in {"pin", "pinterest"}:
        return "pinterest"
    if v in {"snap", "snapchat"}:
        return "snapchat"
    return v


def build_make_payload(post: Dict[str, Any]) -> Dict[str, Any]:
    network = normalize_network(post.get("network") or post.get("reseau"))
    return {
        "secret": MAKE_SHARED_SECRET,
        "post_id": post.get("post_id") or post.get("id"),
        "user_id": post.get("user_id"),
        "network": network,
        "status": str(post.get("status") or post.get("statut") or "scheduled"),
        "caption": post.get("caption") or "",
        "base_caption": post.get("base_caption") or "",
        "cta": post.get("cta") or "",
        "hashtags": post.get("hashtags") or "",
        "content": post.get("content") or post.get("contenu") or {},
        "media_url": post.get("media_url") or post.get("media") or "",
        "slides": post.get("slides") or [],
        "scheduled_at": post.get("scheduled_at") or post.get("date_programmee"),
        "sent_at": datetime.utcnow().isoformat(),
        "source": "lgd_planner",
    }


def _mock_response(post: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_make_payload(post)
    if payload["network"] not in SUPPORTED_NETWORKS:
        return {
            "ok": False,
            "mode": "mock",
            "status": "failed",
            "message": f"Network not supported: {payload['network']}",
            "payload": payload,
        }
    return {
        "ok": True,
        "mode": "mock",
        "status": "sent_to_make",
        "message": "Mock dispatch exécuté avec succès",
        "external_id": f"mock-{payload['network']}-{payload['post_id']}",
        "payload": payload,
    }


def send_to_make(post: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_make_payload(post)

    if payload["network"] not in SUPPORTED_NETWORKS:
        return {
            "ok": False,
            "mode": "mock" if not MAKE_WEBHOOK_URL else "webhook",
            "status": "failed",
            "message": f"Network not supported: {payload['network']}",
            "payload": payload,
        }

    if not MAKE_WEBHOOK_URL:
        return _mock_response(post)

    response = requests.post(
        MAKE_WEBHOOK_URL,
        json=payload,
        timeout=20,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()

    data: Optional[Dict[str, Any]]
    try:
        data = response.json()
        if not isinstance(data, dict):
            data = {"raw": data}
    except Exception:
        data = {"raw": response.text}

    return {
        "ok": True,
        "mode": "webhook",
        "status": str(data.get("status") or "sent_to_make"),
        "message": str(data.get("message") or "Dispatch vers Make effectué"),
        "external_id": data.get("external_id"),
        "payload": payload,
        "response": data,
    }
