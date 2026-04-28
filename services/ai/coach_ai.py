from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple


# -----------------------------------------------------------------------------
# Coach AI (LGD) — Real LLM when OPENAI_API_KEY is present, otherwise fallback.
# IMPORTANT:
# - Signature MUST stay compatible with routes/coach_ia.py
# - No refactor outside this file.
# - Returns a dict to optionally carry usage info, but callers can accept str too.
# -----------------------------------------------------------------------------


FALLBACK_REPLY = (
    "Je suis Alex. Donne-moi :\n"
    "1) ton objectif (en 1 phrase)\n"
    "2) ta niche\n"
    "3) ton offre actuelle\n\n"
    "Et je te fais un plan d'exécution simple en 3 étapes."
)


def _clean(s: Any) -> str:
    return str(s or "").strip()


def _system_prompt(mode: str, focus: str, plan: str) -> str:
    mode_n = _clean(mode).lower() or "premium"
    focus_n = _clean(focus).lower() or "jour"
    plan_n = _clean(plan).lower() or "essentiel"

    return (
        "Tu es Alex V2, coach IA premium de Le Générateur Digital. "
        "Tu es à la fois stratège business, copywriter, coach d'exécution et conseiller anti-dispersion. "
        "Tu réponds en français, avec un ton direct, humain, rassurant et orienté résultat.\n\n"
        f"Contexte: mode={mode_n}, focus={focus_n}, plan={plan_n}.\n\n"
        "Méthode invisible V3 : avant de répondre, identifie l'objectif réel, le blocage, le niveau utilisateur, "
        "le levier business, la prochaine action rentable, le risque de dispersion et le niveau d'urgence. "
        "Ne montre pas ce raisonnement sauf demande.\n\n"
        "Règles de réponse :\n"
        "- pas de blabla, pas de théorie générale, pas de disclaimer inutile ;\n"
        "- donne une réponse courte mais utile ;\n"
        "- propose un plan concret en étapes simples ;\n"
        "- parle comme un coach qui veut faire avancer, pas comme une IA générique ;\n"
        "- si l'utilisateur est perdu, donne UNE priorité claire ;\n"
        "- si l'utilisateur demande trop de choses, coupe en priorité rentable ;\n"
        "- propose parfois un angle marketing plus fort si la demande est trop générique ;\n"
        "- toujours finir par un next step unique ou une question de clarification vraiment utile."
    )


def _extract_usage(usage: Any) -> Optional[Dict[str, int]]:
    try:
        if not usage:
            return None
        # OpenAI responses typically have: prompt_tokens, completion_tokens, total_tokens
        pt = int(getattr(usage, "prompt_tokens", None) or usage.get("prompt_tokens") or 0)
        ct = int(getattr(usage, "completion_tokens", None) or usage.get("completion_tokens") or 0)
        tt = int(getattr(usage, "total_tokens", None) or usage.get("total_tokens") or (pt + ct))
        return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    except Exception:
        return None


def generate_coach_reply(
    *,
    message: str,
    mode: str,
    focus: str,
    context: Dict[str, Any] | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    plan: str = "essentiel",
) -> Dict[str, Any] | str:
    """Generate a coach reply.

    Returns either:
      - dict: {reply: str, source: str, usage?: {total_tokens:int,...}}
      - or str (legacy)
    """
    msg = _clean(message)
    if not msg:
        return {"reply": FALLBACK_REPLY, "source": "fallback"}

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
    if not api_key:
        return {"reply": FALLBACK_REPLY, "source": "fallback_no_key"}

    # Best-effort OpenAI call. Keep it optional to avoid backend crash if package missing.
    try:
        # New OpenAI python SDK
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)

        sys = _system_prompt(mode=mode, focus=focus, plan=plan)

        # Light context injection (safe)
        ctx_bits = []
        if user_email:
            ctx_bits.append(f"user_email={_clean(user_email)}")
        if user_id is not None:
            ctx_bits.append(f"user_id={int(user_id)}")
        if context:
            # Résumé léger du contexte utilisateur, sans dump massif.
            safe_ctx = []
            for key in ("goal", "niche", "offer", "audience", "stage", "last_action"):
                value = context.get(key) if isinstance(context, dict) else None
                if value:
                    safe_ctx.append(f"{key}={_clean(value)[:120]}")
            ctx_bits.append("context=" + " | ".join(safe_ctx) if safe_ctx else "context_present=1")
        if ctx_bits:
            sys = sys + "\n\n" + "Meta: " + ", ".join(ctx_bits)

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_COACH", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": msg},
            ],
            temperature=0.48,
            max_tokens=800,
        )

        reply = ""
        try:
            reply = (resp.choices[0].message.content or "").strip()
        except Exception:
            reply = ""

        if not reply:
            return {"reply": FALLBACK_REPLY, "source": "fallback_empty"}

        usage = _extract_usage(getattr(resp, "usage", None))
        return {"reply": reply, "source": "openai", "usage": usage}

    except Exception as e:
        # Never crash the backend route; return fallback
        return {"reply": FALLBACK_REPLY, "source": "fallback_error"}
