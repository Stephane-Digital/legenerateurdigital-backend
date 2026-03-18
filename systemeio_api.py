import requests
import os

SYSTEME_IO_API_KEY = os.getenv("SYSTEME_IO_API_KEY")
SYSTEME_IO_API_URL = "https://api.systeme.io/api"

def get_user_plan(email: str) -> str:
    """
    Retourne le plan système.io d'un utilisateur (free / starter / premium).
    """

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": SYSTEME_IO_API_KEY,
    }

    response = requests.get(
        f"{SYSTEME_IO_API_URL}/contacts",
        params={"email": email},
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        return "free"

    data = response.json()
    contacts = data.get("data", [])

    if not contacts:
        return "free"

    contact = contacts[0]

    # Système.io utilise des tags ou des offres
    tags = contact.get("tags", [])
    offers = contact.get("offers", [])

    # 🔥 REGLES À ADAPTER SELON TES OFFRES
    if "lgd-premium" in tags or "lgd-premium" in offers:
        return "premium"

    if "lgd-starter" in tags or "lgd-starter" in offers:
        return "starter"

    return "free"
