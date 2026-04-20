from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db

from services.ai_quota_service import get_or_create_quota

router = APIRouter(prefix="/webhooks/systemeio", tags=["Systeme.io Webhook"])


# ======================================================
# 🔐 CONFIG
# ======================================================
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


# ======================================================
# 🧠 USER LOOKUP
# ======================================================
def get_user_by_email(db: Session, email: str):
    query = text("SELECT id FROM users WHERE email = :email LIMIT 1")
    result = db.execute(query, {"email": email}).fetchone()
    return result[0] if result else None


def update_user_plan(db: Session, user_id: int, plan: str):
    query = text("UPDATE users SET plan = :plan WHERE id = :uid")
    db.execute(query, {"plan": plan, "uid": user_id})


# ======================================================
# 🔁 QUOTA RESET
# ======================================================
def reset_user_quota(db: Session, user_id: int, plan: str):
    quota = get_or_create_quota(db, user_id, feature="coach")

    new_limit = _limit_for_plan(plan)

    # reset usage
    if hasattr(quota, "tokens_used"):
        quota.tokens_used = 0

    # update credits (monthly limit)
    if hasattr(quota, "credits"):
        quota.credits = new_limit

    if hasattr(quota, "plan"):
        quota.plan = plan

    db.add(quota)


# ======================================================
# 🚀 WEBHOOK ENTRYPOINT
# ======================================================
@router.post("/")
async def systemeio_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        print("WEBHOOK SIO DATA:", data)

        email = data.get("email")
        offer = data.get("offer_name") or data.get("offer")

        if not email or not offer:
            raise HTTPException(status_code=400, detail="Payload invalide")

        plan = PLAN_MAP.get(str(offer).upper())
        if not plan:
            raise HTTPException(status_code=400, detail="Offre inconnue")

        user_id = get_user_by_email(db, email)

        if not user_id:
            print("USER NOT FOUND:", email)
            return {"status": "ignored"}

        # 1️⃣ update plan
        update_user_plan(db, user_id, plan)

        # 2️⃣ reset quota
        reset_user_quota(db, user_id, plan)

        db.commit()

        print(f"USER {user_id} → PLAN {plan} ACTIVATED")

        return {"status": "success"}

    except Exception as e:
        print("WEBHOOK ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
