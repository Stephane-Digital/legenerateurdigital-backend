# routes/ai.py

from fastapi import APIRouter, Query
from schemas.ai_schema import AIGenerateRequest, AIGenerateResponse
from services.ai_service import generate_ai_content

router = APIRouter(prefix="/ai", tags=["AI"])

# 👉 Route principale en POST (pour le front / API)
@router.post("/generate", response_model=AIGenerateResponse)
def generate_ai_route(data: AIGenerateRequest):
    return generate_ai_content(data)

# 👉 Route GET de test (pour ton navigateur)
@router.get("/generate", response_model=AIGenerateResponse)
def generate_ai_test(
    prompt: str = Query("Test LGD – dis bonjour à Stéphane 😄"),
    type: str = Query("default")
):
    data = AIGenerateRequest(prompt=prompt, type=type)
    return generate_ai_content(data)
