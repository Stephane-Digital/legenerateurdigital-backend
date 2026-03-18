from __future__ import annotations

import base64
from typing import Any, Dict, Optional

import requests

GRAPH_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class FacebookPublishError(Exception):
    pass


def _pick_message(content: Dict[str, Any]) -> str:
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


def _pick_image_base64(content: Dict[str, Any]) -> Optional[str]:
    for key in ("image_base64", "imageBase64"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def publish_facebook_page(*, page_id: str, page_access_token: str, content: Dict[str, Any]) -> Dict[str, Any]:
    if not page_id or not page_access_token:
        raise FacebookPublishError("Connexion Facebook invalide : page_id ou page_access_token manquant")

    message = _pick_message(content)
    image_url = _pick_image_url(content)
    image_base64 = _pick_image_base64(content)

    if image_url:
        response = requests.post(
            f"{GRAPH_BASE}/{page_id}/photos",
            data={
                "url": image_url,
                "caption": message,
                "access_token": page_access_token,
            },
            timeout=60,
        )
        if response.status_code >= 300:
            raise FacebookPublishError(f"Facebook photo publish failed: {response.text}")
        payload = response.json() or {}
        return {
            "success": True,
            "platform": "facebook",
            "platform_post_id": payload.get("post_id") or payload.get("id"),
            "raw_response": payload,
        }

    if image_base64:
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            raise FacebookPublishError(f"image_base64 invalide: {e}")

        response = requests.post(
            f"{GRAPH_BASE}/{page_id}/photos",
            data={
                "caption": message,
                "access_token": page_access_token,
            },
            files={"source": ("image.jpg", image_bytes)},
            timeout=60,
        )
        if response.status_code >= 300:
            raise FacebookPublishError(f"Facebook binary photo publish failed: {response.text}")
        payload = response.json() or {}
        return {
            "success": True,
            "platform": "facebook",
            "platform_post_id": payload.get("post_id") or payload.get("id"),
            "raw_response": payload,
        }

    if not message:
        raise FacebookPublishError("Aucun contenu publiable Facebook : caption/texte/image manquant")

    response = requests.post(
        f"{GRAPH_BASE}/{page_id}/feed",
        data={
            "message": message,
            "access_token": page_access_token,
        },
        timeout=60,
    )
    if response.status_code >= 300:
        raise FacebookPublishError(f"Facebook text publish failed: {response.text}")
    payload = response.json() or {}
    return {
        "success": True,
        "platform": "facebook",
        "platform_post_id": payload.get("id"),
        "raw_response": payload,
    }
