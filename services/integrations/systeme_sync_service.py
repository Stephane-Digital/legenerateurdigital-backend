
from typing import Dict, Any
from services.integrations.systeme_io_client import SystemeIOClient


def fetch_systeme_contacts() -> Dict[str, Any]:
    """
    Récupère les contacts Systeme.io
    """
    client = SystemeIOClient()
    return client._request("GET", "/contacts")


def fetch_systeme_tags() -> Dict[str, Any]:
    """
    Récupère les tags Systeme.io
    """
    client = SystemeIOClient()
    return client._request("GET", "/tags")


def fetch_systeme_campaigns() -> Dict[str, Any]:
    """
    Récupère les campagnes Systeme.io
    """
    client = SystemeIOClient()
    return client._request("GET", "/campaigns")
