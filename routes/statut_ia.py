# =============================================================
# 🤖 ROUTE IA — DÉTERMINATION DU STATUT JURIDIQUE (LGD)
# Compatible avec les clés OpenAI “sk-proj” et “sk-admin”
# =============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
import json

router = APIRouter(prefix="/statut", tags=["Statut IA"])
load_dotenv()

class StatutRequest(BaseModel):
    activite: str
    nombre_associes: int
    capital_initial: float
    risque: str

@router.post("/")
def determiner_statut(request: StatutRequest):
    try:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise HTTPException(status_code=500, detail="Clé API OpenAI manquante dans le .env.")

        # ✅ Endpoint universel (fonctionne avec toutes les clés)
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Tu es un expert en création d’entreprise en France."},
                {"role": "user", "content": (
                    f"Propose le statut juridique le plus adapté à une activité '{request.activite}', "
                    f"avec {request.nombre_associes} associé(s), un capital initial de {request.capital_initial} €, "
                    f"et un niveau de risque '{request.risque}'. "
                    f"Explique clairement les avantages et limites du statut recommandé."
                )}
            ],
            "temperature": 0.7,
            "max_tokens": 400
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        data = response.json()
        message = data["choices"][0]["message"]["content"]
        return {"statut_recommande": message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")


# =============================================================
# ✅ Exemple d'appel :
# {
#   "activite": "marketing digital",
#   "nombre_associes": 1,
#   "capital_initial": 2000,
#   "risque": "faible"
# }
# =============================================================
