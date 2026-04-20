from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from services.ai_quota_service import get_or_create_quota

router = APIRouter(prefix="/webhooks/systemeio", tags=["Systeme.io Webhook"])


PLAN_MAP = {
    "ESSENTIEL": "essentiel",
    "PRO": "pro",
    "ULTIME": "ultime",
}


def _limit_for_plan(plan: str) -> int:
    p = (plan or "").lower()
    if "ult" in p:
        return 2_500_000
    if "pro" in p:
        return 1_000_000
    return 400_000


def get_user_by_email(db: Session, email: str):
    query = text("SELECT id FROM users WHERE email = :email LIMIT 1")
    result = db.execute(query, {"email": email}).fetchone()
    return result[0] if result else None


def _users_has_column(db: Session, column_name: str) -> bool:
    query = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name = :column_name
        LIMIT 1
        """
    )
    result = db.execute(query, {"column_name": column_name}).fetchone()
    return bool(result)


def update_user_plan_if_possible(db: Session, user_id: int, plan: str):
    if not _users_has_column(db, "plan"):
        print("WEBHOOK SIO: users.plan absent → skip update users.plan")
        return

    query = text("UPDATE users SET plan = :plan WHERE id = :uid")
    db.execute(query, {"plan": plan, "uid": user_id})


def reset_user_quota(db: Session, user_id: int, plan: str):
    quota = get_or_create_quota(db, user_id, feature="coach")
    new_limit = _limit_for_plan(plan)

    if hasattr(quota, "tokens_used"):
        quota.tokens_used = 0

    if hasattr(quota, "credits"):
        quota.credits = new_limit

    if hasattr(quota, "plan"):
        quota.plan = plan

    db.add(quota)


@router.post("/")
async def systemeio_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        print("WEBHOOK SIO DATA:", data)

        email = str(data.get("email") or "").strip().lower()
        offer = str(data.get("offer_name") or data.get("offer") or "").strip()

        if not email or not offer:
            raise HTTPException(status_code=400, detail="Payload invalide")

        plan = PLAN_MAP.get(offer.upper())
        if not plan:
            raise HTTPException(status_code=400, detail="Offre inconnue")

        user_id = get_user_by_email(db, email)
        if not user_id:
            print("WEBHOOK SIO: USER NOT FOUND:", email)
            return {"status": "ignored", "reason": "user_not_found"}

        update_user_plan_if_possible(db, user_id, plan)
        reset_user_quota(db, user_id, plan)

        db.commit()

        print(f"WEBHOOK SIO: USER {user_id} → PLAN {plan} ACTIVATED")
        return {"status": "success", "user_id": user_id, "plan": plan}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("WEBHOOK ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

