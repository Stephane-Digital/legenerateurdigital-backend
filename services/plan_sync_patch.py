# PATCH LGD PLAN SYNC
# inject quota plan into auth user response

from sqlalchemy.orm import Session
from sqlalchemy import text

def get_user_plan_with_quota(db: Session, user: dict):
    try:
        row = db.execute(
            text("SELECT plan FROM ai_quotas WHERE user_id = :uid LIMIT 1"),
            {"uid": user["id"]},
        ).mappings().first()

        if row and row.get("plan"):
            user["plan"] = row["plan"]
    except Exception as e:
        print("PLAN_SYNC_ERROR:", str(e))

    return user
