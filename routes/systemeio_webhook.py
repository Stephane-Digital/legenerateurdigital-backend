import json
import hmac
import hashlib
from typing import Any, Optional, Set

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from config.settings import settings
from services.ai_quota_service import get_or_create_quota
from services.trial_access_service import upsert_trial_pending


router = APIRouter(prefix="/webhooks/systemeio", tags=["Systeme.io Webhook"])


# ======================================================
# 🔐 SIGNATURE
# ======================================================
def _compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


# ======================================================
# 🧠 PLAN MAPPING (via ENV)
# ======================================================
def _ids_from_settings(name: str) -> Set[int]:
    raw = getattr(settings, name, "") or ""
    raw = str(raw).strip()
    if not raw:
        return set()

    out: Set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except Exception:
            pass
    return out


def _resolve_plan(priceplan_id: Optional[int]) -> Optional[str]:
    if priceplan_id is None:
        return None

    if priceplan_id in _ids_from_settings("SYSTEMEIO_PRICEPLAN_ULTIME_IDS"):
        return "ultime"

    if priceplan_id in _ids_from_settings("SYSTEMEIO_PRICEPLAN_PRO_IDS"):
        return "pro"

    if priceplan_id in _ids_from_settings("SYSTEMEIO_PRICEPLAN_ESSENTIEL_IDS"):
        return "essentiel"

    return None


# ======================================================
# 🎯 LIMITES TOKENS
# ======================================================
def _limit_for_plan(plan: str) -> int:
    if plan == "ultime":
        return 2_500_000
    if plan == "pro":
        return 1_000_000
    if plan == "essentiel":
        return 400_000
    if plan == "trial":
        return 10_000
    return 0


# ======================================================
# 👤 USER
# ======================================================
def _get_user_by_email(db: Session, email: str):
    from sqlalchemy import text

    result = db.execute(
        text("SELECT id FROM users WHERE email = :email LIMIT 1"),
        {"email": email},
    ).fetchone()

    return result[0] if result else None


# ======================================================
# 🔁 UPDATE PLAN + QUOTA
# ======================================================
def _apply_plan(db: Session, user_id: int, plan: str):
    from sqlalchemy import text

    # 👉 update users.plan si colonne existe
    try:
        db.execute(
            text("UPDATE users SET plan = :plan WHERE id = :uid"),
            {"plan": plan, "uid": user_id},
        )
    except Exception:
        print("⚠️ users.plan absent, skip")

    limit_tokens = _limit_for_plan(plan)

    # ✅ IMPORTANT : on synchronise les 2 buckets utilisés par LGD
    for feature_name in ("coach", "global"):
        quota = get_or_create_quota(db, user_id, feature=feature_name)

        if hasattr(quota, "tokens_used"):
            quota.tokens_used = 0

        if hasattr(quota, "credits"):
            quota.credits = limit_tokens

        if hasattr(quota, "plan"):
            quota.plan = plan

        db.add(quota)


# ======================================================
# 🧪 TRIAL DETECTION
# ======================================================
def _payload_text(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False).lower()
    except Exception:
        return str(payload).lower()


def _is_trial_event(event: str, payload: dict) -> bool:
    event_value = str(event or "").strip().lower()
    raw = _payload_text(payload)

    trial_keywords = (
        "trial",
        "essai",
        "7 jours",
        "7j",
        "gratuit",
        "free trial",
        "essai gratuit",
    )

    if any(keyword in event_value for keyword in trial_keywords):
        return True

    if any(keyword in raw for keyword in trial_keywords):
        return True

    return False


# ======================================================
# 🚀 WEBHOOK
# ======================================================
@router.post("/")
async def systemeio_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        secret = (settings.SYSTEMEIO_WEBHOOK_SECRET or "").strip()

        if not secret:
            raise HTTPException(status_code=500, detail="Webhook secret missing")

        raw = await request.body()

        signature = request.headers.get("X-Webhook-Signature", "")
        event = (request.headers.get("X-Webhook-Event", "") or "").upper()

        expected = _compute_signature(secret, raw)

        if not signature or not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

        payload = json.loads(raw.decode("utf-8"))

        print("🔥 WEBHOOK SIO PAYLOAD:", payload)
        print("🔥 EVENT:", event)

        # ==================================================
        # 📧 EMAIL
        # ==================================================
        customer = payload.get("customer") or {}
        email = (customer.get("email") or payload.get("email") or "").strip().lower()

        if not email:
            raise HTTPException(status_code=400, detail="Missing email")

        # ==================================================
        # 🧪 TRIAL PENDING / ACTIVE
        # ==================================================
        if _is_trial_event(event, payload):
            trial_meta = upsert_trial_pending(
                db=db,
                email=email,
                full_name=(
                    customer.get("name")
                    or payload.get("name")
                    or payload.get("full_name")
                    or payload.get("fullName")
                    or None
                ),
                source_event=event,
                payload=payload,
            )

            user_id = _get_user_by_email(db, email)

            if user_id:
                _apply_plan(db, user_id, "trial")
                db.commit()

                print(f"🧪 TRIAL ACTIVE EXISTING USER: {email}")

                return {
                    "status": "trial_active_existing_user",
                    "plan": "trial",
                    "email": email,
                }

            db.commit()

            print(f"🧪 TRIAL PENDING CREATED: {email}")

            return {
                "status": "trial_pending",
                "email": email,
                "trial_ends_at": trial_meta.get("trial_ends_at"),
            }

        # ==================================================
        # 💳 PLAN
        # ==================================================
        priceplan = payload.get("pricePlan") or {}
        priceplan_id = priceplan.get("id")

        try:
            priceplan_id = int(priceplan_id)
        except Exception:
            priceplan_id = None

        plan = _resolve_plan(priceplan_id)

        # ==================================================
        # 👤 USER
        # ==================================================
        user_id = _get_user_by_email(db, email)

        if not user_id:
            print("❌ USER NOT FOUND:", email)
            return {"status": "ignored", "reason": "user_not_found"}

        # ==================================================
        # 🟢 NEW SALE
        # ==================================================
        if event == "NEW_SALE":
            if not plan:
                print("❌ PLAN NOT FOUND:", priceplan_id)
                return {"status": "ignored", "reason": "unknown_plan"}

            _apply_plan(db, user_id, plan)
            db.commit()

            print(f"✅ USER {user_id} → PLAN {plan}")

            return {"status": "success", "plan": plan}

        # ==================================================
        # 🔴 CANCEL
        # ==================================================
        if event == "SALE_CANCELED":
            _apply_plan(db, user_id, "essentiel")
            db.commit()

            print(f"🔴 USER {user_id} → PLAN essentiel")

            return {"status": "canceled", "plan": "essentiel"}

        return {"status": "ignored", "event": event}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        print("❌ WEBHOOK ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
