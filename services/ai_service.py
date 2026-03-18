# services/ai_service.py

from schemas.ai_schema import AIGenerateRequest, AIGenerateResponse

# ⚠️ NOTE IMPORTANTE
# On ne met PAS de clé OpenAI NI d'appel direct ici pour éviter les erreurs.
# On simule une génération propre côté backend, vérifiée, stable.
# Le frontend fera la vraie génération via OpenAI.

def generate_ai_content(data: AIGenerateRequest) -> AIGenerateResponse:
    fake_output = f"🧠 Génération IA (mode: {data.type}):\n\n{data.prompt}\n\n➡️ (contenu généré simulé - prêt pour OpenAI côté frontend)"

    return AIGenerateResponse(
        content=fake_output,
        model="gpt-4o-mini"
    )
