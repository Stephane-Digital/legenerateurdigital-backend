# C:\LGD\legenerateurdigital_backend\services\content_engine_service.py

import os
from openai import OpenAI
from config.settings import settings

# ============================================================
# INITIALISATION OPENAI (v1+)
# ============================================================

def _get_api_key() -> str:
    # Priorité: env > settings
    key = os.getenv("OPENAI_API_KEY", "").strip() or str(getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    return key

def _get_model(default: str = "gpt-4o-mini") -> str:
    # Tu peux override sans toucher au code :
    # OPENAI_MODEL=gpt-4o-mini
    # OPENAI_MODEL_REWRITE=gpt-4o-mini
    # OPENAI_MODEL_SUMMARY=gpt-4o-mini
    return (default or "gpt-4o-mini").strip()

def _client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise Exception("OPENAI_API_KEY manquante (dans .env ou settings)")
    return OpenAI(api_key=api_key)

def _extract_text(resp) -> str:
    try:
        out = (resp.choices[0].message.content or "").strip()
        return out
    except Exception:
        return ""


# ============================================================
# 🧠 GENERATE AI TEXT
# ============================================================
def generate_ai_text(prompt: str, tone: str = "default", language: str = "fr") -> str:
    """
    Génère un texte avec l'IA en fonction du prompt.
    Compatible openai>=1.0.0
    """

    system_prompt = (
        f"Tu es un assistant expert en rédaction marketing ton '{tone}'. "
        f"Tu écris toujours en langue : {language}. "
        f"Ton style doit être clair, fluide et impactant."
    )

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL", "").strip() or os.getenv("OPENAI_MODEL_TEXT", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            # max_tokens reste optionnel en v1 — on garde l'intention initiale
            max_tokens=300,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur AI Text: {str(e)}")


# ============================================================
# ✍️ REWRITE TEXT
# ============================================================
def rewrite_text(text: str, tone: str | None = None, max_length: int | None = None) -> str:
    """
    Réécrit un texte en version améliorée, plus claire et professionnelle.

    ✅ LGD FIX:
    - Supporte tone + max_length (optionnels) sans casser l'ancienne signature.
    - Compatible openai>=1.0.0
    """

    tone_txt = (tone or "").strip()
    max_len = int(max_length) if max_length is not None else None

    instr = "Réécris ce texte de manière plus professionnelle, claire et fluide."
    if tone_txt:
        instr += f" Adopte un ton: {tone_txt}."
    if max_len and max_len > 0:
        instr += f" Limite-toi à environ {max_len} caractères."

    user_prompt = f"{instr}\n\nTEXTE À RÉÉCRIRE :\n{text}"

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL_REWRITE", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en réécriture marketing."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur Rewrite: {str(e)}")


# ============================================================
# 📝 SUMMARIZE TEXT
# ============================================================
def summarize_text(text: str) -> str:
    """
    Produit un résumé clair et concis du texte fourni.
    Compatible openai>=1.0.0
    """
    prompt = f"Résume ce texte en 5 lignes maximum :\n\n{text}"

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL_SUMMARY", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en synthèse."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=200,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur Résumé: {str(e)}")
