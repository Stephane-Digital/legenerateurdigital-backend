from __future__ import annotations

from sqlalchemy.orm import Session

from services.ia_quota_engine import estimate_tokens, consume_tokens


def charge_coach_tokens(
    *,
    db: Session,
    user_id: int,
    plan: str,
    user_message: str,
    ai_answer: str,
) -> dict:
    """
    Décompte réel pour Coach Alex
    """

    full_text = f"{user_message}\n{ai_answer}"
    tokens = estimate_tokens(full_text)

    result = consume_tokens(
        db=db,
        user_id=user_id,
        plan=plan,
        module="coach",
        tokens=tokens,
        feature="coach_chat",
    )

    return result
