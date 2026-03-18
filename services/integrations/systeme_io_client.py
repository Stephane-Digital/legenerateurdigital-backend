import os
import requests


class SystemeIOClient:
    """
    Client minimal pour communiquer avec l'API Systeme.io
    Utilisé uniquement par le module Emailing IA LGD
    """

    def __init__(self):
        self.api_key = os.getenv("SYSTEME_IO_API_KEY")
        self.base_url = os.getenv("SYSTEME_IO_API_BASE_URL")

        if not self.api_key:
            raise ValueError("SYSTEME_IO_API_KEY manquante")

        if not self.base_url:
            raise ValueError("SYSTEME_IO_API_BASE_URL manquante")

        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def create_contact(self, email: str, first_name: str = "", last_name: str = "", tags=None):
        """
        Crée un contact dans Systeme.io
        """
        url = f"{self.base_url}/contacts"

        payload = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tags": tags or [],
        }

        response = requests.post(url, json=payload, headers=self.headers)

        if response.status_code not in (200, 201):
            raise Exception(f"Erreur Systeme.io: {response.text}")

        return response.json()

    def add_tag(self, contact_id: str, tag: str):
        """
        Ajoute un tag à un contact
        """
        url = f"{self.base_url}/contacts/{contact_id}/tags"

        payload = {
            "tag": tag
        }

        response = requests.post(url, json=payload, headers=self.headers)

        if response.status_code not in (200, 201):
            raise Exception(f"Erreur ajout tag Systeme.io: {response.text}")

        return response.json()
