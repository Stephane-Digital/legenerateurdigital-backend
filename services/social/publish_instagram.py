from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

GRAPH_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class InstagramPublishError(Exception):
    pass


def _pick_caption(content: Dict[str, Any]) -> str:
    for key in ("caption", "text", "message", "contenu", "content"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_image_url(content: Dict[str, Any]) -> Optional[str]:
    candidates = [
        content.get("image_url"),
        content.get("media_url"),
        content.get("imageUrl"),
        content.get("mediaUrl"),
    ]
    slides = content.get("slides")
    if isinstance(slides, list):
        for slide in slides:
            if isinstance(slide, dict):
                for key in ("image_url", "media_url", "preview_url", "thumbnail_url"):
                    value = slide.get(key)
                    if isinstance(value, str) and value.strip():
                        candidates.append(value.strip())
    for value in candidates:
        if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
            return value.strip()
    return None


def _wait_media_ready(ig_user_id: str, creation_id: str, access_token: str) -> None:
    for _ in range(10):
        res = requests.get(
            f"{GRAPH_BASE}/{creation_id}",
            params={
                "fields": "status_code",
                "access_token": access_token,
            },
            timeout=30,
        )
        if res.status_code >= 300:
            raise InstagramPublishError(f"Instagram media status failed: {res.text}")
        status_code = str((res.json() or {}).get("status_code") or "")
        if status_code in {"FINISHED", "PUBLISHED", "READY"}:
            return
        if status_code in {"ERROR", "EXPIRED"}:
            raise InstagramPublishError(f"Instagram media container invalid: {res.text}")
        time.sleep(2)


def publish_instagram_image(*, ig_user_id: str, access_token: str, content: Dict[str, Any]) -> Dict[str, Any]:
    if not ig_user_id or not access_token:
        raise InstagramPublishError("Connexion Instagram invalide : ig_user_id ou access_token manquant")

    image_url = _pick_image_url(content)
    if not image_url:
        raise InstagramPublishError(
            "Instagram nécessite une image publique via image_url/media_url. "
            "Le base64 direct n'est pas supporté par ce flux."
        )

    caption = _pick_caption(content)

    create = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=60,
    )
    if create.status_code >= 300:
        raise InstagramPublishError(f"Instagram create media failed: {create.text}")

    create_payload = create.json() or {}
    creation_id = create_payload.get("id")
    if not creation_id:
        raise InstagramPublishError(f"Instagram create media returned no id: {create.text}")

    _wait_media_ready(ig_user_id=ig_user_id, creation_id=creation_id, access_token=access_token)

    publish = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=60,
    )
    if publish.status_code >= 300:
        raise InstagramPublishError(f"Instagram publish failed: {publish.text}")

    publish_payload = publish.json() or {}
    return {
        "success": True,
        "platform": "instagram",
        "platform_post_id": publish_payload.get("id"),
        "creation_id": creation_id,
        "raw_response": {
            "create": create_payload,
            "publish": publish_payload,
        },
    }
