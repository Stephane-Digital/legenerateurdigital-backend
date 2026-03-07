from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import date

from models.daily_usage_model import DailyUsage


def check_email_generation_quota(db: Session, user):
    today = date.today()

    usage = (
        db.query(DailyUsage)
        .filter(DailyUsage.user_id == user.id, DailyUsage.date == today)
        .first()
    )

    if not usage:
        usage = DailyUsage(user_id=user.id, date=today, email_generations=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)

    limit = None
    if user.plan == "FREE":
        limit = 5
    elif user.plan == "PRO":
        limit = 50
    elif user.plan == "BUSINESS":
        limit = None

    if limit is not None and usage.email_generations >= limit:
        raise HTTPException(
            403,
            f"Limite quotidienne atteinte ({limit} emails). Passez au plan supérieur."
        )

    usage.email_generations += 1
    db.commit()
