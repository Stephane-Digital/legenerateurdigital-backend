from __future__ import annotations
import os
from typing import Tuple, Any

from fastapi import HTTPException


# IMPORTANT :
# On ne doit JAMAIS créer le client OpenAI au chargement du module
# sinon le backend crash sans clé


def _get_openai_client():
    """
    Lazy loader sécurisé.
    Le backend doit fonctionner même sans OPENAI_API_KEY.
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")

    if not api_key:
        return None

    try:
        from openai import OpenAI  # import local volontaire
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def run_ai_and_consume(
    *,
    db,
    user,
    system_prompt: str,
    user_prompt: str,
    feature: str = "coach",
) -> Tuple[str, dict]:
    """
    Lance l'IA + retourne (reply, usage)
    NE DOIT JAMAIS FAIRE CRASH LE BACKEND
    """

    client = _get_openai_client()

    # ---------- PAS DE CLE API ----------
    if client is None:
        raise RuntimeError("OPENAI_DISABLED")

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_COACH", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=700,
        )

        reply = (response.choices[0].message.content or "").strip()

        usage = getattr(response, "usage", None) or {}
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }

        return reply, usage_dict

    except Exception as e:
        # IMPORTANT : on ne bloque jamais LGD
        raise RuntimeError("OPENAI_RUNTIME_ERROR") from e
