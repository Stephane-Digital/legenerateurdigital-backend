import json
import hmac
import hashlib
from typing import Any, Optional, Set

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from config.settings import settings
from services.ai_quota_service import sync_plan_quotas
from services.pending_access_service import upsert_pending_access

router = APIRouter(prefix="/webhooks/systemeio", tags=["Systeme.io Webhook"])


def _compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


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


def _get_user_by_email(db: Session, email: str):
    from sqlalchemy import text

    result = db.execute(
        text("SELECT id FROM users WHERE LOWER(email) = LOWER(:email) LIMIT 1"),
        {"email": email},
    ).fetchone()

    return result[0] if result else None


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

        customer = payload.get("customer") or {}
        email = (
            customer.get("email")
            or payload.get("email")
            or payload.get("contact_email")
            or ""
        ).strip().lower()

        if not email:
            raise HTTPException(status_code=400, detail="Missing email")

        full_name = (
            customer.get("name")
            or payload.get("name")
            or payload.get("full_name")
            or payload.get("fullName")
            or None
        )

        if _is_trial_event(event, payload):
            pending = upsert_pending_access(
                db=db,
                email=email,
                full_name=full_name,
                access_type="trial",
                plan="trial",
                source_event=event,
                payload=payload,
                duration_days=7,
            )

            user_id = _get_user_by_email(db, email)
            if user_id:
                sync_plan_quotas(db=db, user_id=int(user_id), plan="trial")
                db.commit()
                return {
                    "status": "trial_active_existing_user",
                    "plan": "trial",
                    "email": email,
                }

            db.commit()
            return {
                "status": "trial_pending",
                "email": email,
                "trial_ends_at": pending.get("ends_at"),
            }

        priceplan = payload.get("pricePlan") or {}
        priceplan_id = priceplan.get("id")

        try:
            priceplan_id = int(priceplan_id)
        except Exception:
            priceplan_id = None

        plan = _resolve_plan(priceplan_id)
        user_id = _get_user_by_email(db, email)

        if event == "NEW_SALE":
            if not plan:
                return {"status": "ignored", "reason": "unknown_plan"}

            if user_id:
                sync_plan_quotas(db=db, user_id=int(user_id), plan=plan)
                db.commit()
                return {"status": "success", "plan": plan}

            pending = upsert_pending_access(
                db=db,
                email=email,
                full_name=full_name,
                access_type="paid",
                plan=plan,
                source_event=event,
                payload=payload,
                duration_days=None,
            )
            db.commit()

            return {
                "status": "paid_pending",
                "email": email,
                "plan": plan,
                "pending": pending,
            }

        if event == "SALE_CANCELED":
            if not user_id:
                return {"status": "ignored", "reason": "user_not_found"}

            sync_plan_quotas(db=db, user_id=int(user_id), plan="essentiel")
            db.commit()
            return {"status": "canceled", "plan": "essentiel"}

        return {"status": "ignored", "event": event}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("❌ WEBHOOK ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
