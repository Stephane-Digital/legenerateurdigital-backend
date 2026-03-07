import requests
from config.settings import settings


def rewrite_text(prompt: str):
    endpoint = settings.OPENAI_TEXT_ENDPOINT
    api_key = settings.OPENAI_API_KEY

    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"prompt": prompt}
    )

    return response.json()
