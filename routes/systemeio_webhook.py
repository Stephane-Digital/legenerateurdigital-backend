import json
import hmac
import hashlib
from typing import Optional, Set

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from config.settings import settings


router = APIRouter(prefix="/billing/webhook", tags=["billing"])


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


def _compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def _get_models():
    try:
        from models import User  # type: ignore
    except Exception:
        from models.user_model import User  # type: ignore

    try:
        from models import IAQuota  # type: ignore
    except Exception:
        try:
            from models.ia_quota_model import IAQuota  # type: ignore
        except Exception:
            IAQuota = None  # type: ignore

    return User, IAQuota


def _upsert_plan_on_ia_quota(db: Session, user_id: int, plan: str, active: bool):
    _, IAQuota = _get_models()
    if IAQuota is None:
        raise HTTPException(status_code=500, detail="IAQuota model not found (check models exports).")

    row = db.query(IAQuota).filter(IAQuota.user_id == user_id).first()
    if not row:
        row = IAQuota(user_id=user_id)  # type: ignore
        db.add(row)

    if hasattr(row, "plan"):
        setattr(row, "plan", plan)
    if hasattr(row, "is_active"):
        setattr(row, "is_active", active)
    if hasattr(row, "status"):
        setattr(row, "status", "active" if active else "inactive")

    db.commit()


def _resolve_plan_from_priceplan(priceplan_id: Optional[int]) -> Optional[str]:
    if priceplan_id is None:
        return None

    essentiel_ids = _ids_from_settings("SYSTEMEIO_PRICEPLAN_ESSENTIEL_IDS")
    pro_ids = _ids_from_settings("SYSTEMEIO_PRICEPLAN_PRO_IDS")
    ultime_ids = _ids_from_settings("SYSTEMEIO_PRICEPLAN_ULTIME_IDS")

    if priceplan_id in ultime_ids:
        return "ultime"
    if priceplan_id in pro_ids:
        return "pro"
    if priceplan_id in essentiel_ids:
        return "essentiel"
    return None


@router.post("/systemeio")
async def systemeio_webhook(request: Request):
    """
    Systeme.io webhook:
      - Signature: HMAC SHA256 over RAW request body bytes
      - Headers: X-Webhook-Event, X-Webhook-Signature
    """
    db_gen = get_db()
    db: Session = next(db_gen)

    try:
        secret = (settings.SYSTEMEIO_WEBHOOK_SECRET or "").strip()
        if not secret:
            raise HTTPException(status_code=500, detail="SYSTEMEIO_WEBHOOK_SECRET is not set")

        signature = request.headers.get("X-Webhook-Signature", "") or ""
        event = (request.headers.get("X-Webhook-Event", "") or "").upper()

        raw = await request.body()
        expected = _compute_signature(secret, raw)

        if not signature or not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        customer = payload.get("customer") or {}
        email = (customer.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Missing customer.email")

        priceplan = payload.get("pricePlan") or {}
        priceplan_id = priceplan.get("id")
        try:
            priceplan_id_int = int(priceplan_id) if priceplan_id is not None else None
        except Exception:
            priceplan_id_int = None

        User, _ = _get_models()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {"ok": True, "ignored": True, "reason": "user_not_found", "email": email}

        if event == "NEW_SALE":
            plan = _resolve_plan_from_priceplan(priceplan_id_int)
            if not plan:
                return {
                    "ok": True,
                    "ignored": True,
                    "reason": "unknown_priceplan_id",
                    "email": email,
                    "priceplan_id": priceplan_id_int,
                }

            _upsert_plan_on_ia_quota(db, user.id, plan=plan, active=True)
            return {"ok": True, "event": event, "email": email, "plan": plan}

        if event == "SALE_CANCELED":
            _upsert_plan_on_ia_quota(db, user.id, plan="none", active=False)
            return {"ok": True, "event": event, "email": email, "plan": "none"}

        return {"ok": True, "ignored": True, "reason": "unsupported_event", "event": event}

    finally:
        try:
            db.close()
        except Exception:
            pass
        try:
            next(db_gen)
        except Exception:
            pass
