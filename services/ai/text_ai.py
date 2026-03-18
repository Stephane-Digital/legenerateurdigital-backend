import requests

from config.settings import settings


def rewrite_text(prompt: str):
    endpoint = (settings.OPENAI_TEXT_ENDPOINT or "").strip()
    api_key = (settings.OPENAI_API_KEY or "").strip()

    if not endpoint:
        raise ValueError("OPENAI_TEXT_ENDPOINT manquant dans la configuration.")
    if not api_key:
        raise ValueError("OPENAI_API_KEY manquant dans la configuration.")

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"prompt": prompt},
        timeout=120,
    )

    response.raise_for_status()
    return response.json()
