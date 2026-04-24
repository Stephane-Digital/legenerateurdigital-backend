import json
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional, Set

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from config.settings import settings
from services.ai_quota_service import sync_plan_quotas
from services.pending_access_service import (
    mark_pending_access_active,
    upsert_pending_access,
)

router = APIRouter(prefix="/webhooks/systemeio", tags=["Systeme.io Webhook"])

DEFAULT_FRONT_URL = "https://legenerateurdigital-front.vercel.app"
DEFAULT_TOKEN_HOURS = 24
ROUTE_VERSION = "LGD_TOKEN_SYSTEM_PROD_V2_2026_04_24"


class SystemeioTestPayload(BaseModel):
    event: str
    payload: dict


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
    result = db.execute(
        text("SELECT id FROM users WHERE LOWER(email) = LOWER(:email) LIMIT 1"),
        {"email": email},
    ).fetchone()

    return result[0] if result else None


def _current_database_name(db: Session) -> str:
    try:
        row = db.execute(text("SELECT current_database() AS db_name")).mappings().first()
        return str(row["db_name"]) if row and row.get("db_name") else "unknown"
    except Exception:
        return "unknown"


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


def _frontend_base_url() -> str:
    # PROD ONLY: les liens d'activation envoyés aux clients doivent toujours pointer vers Vercel.
    # On ne lit plus FRONTEND_URL/LGD_FRONT_URL ici pour éviter tout retour accidentel vers localhost.
    return DEFAULT_FRONT_URL.rstrip("/")


def _token_expiration(hours: int) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)


def _ensure_activation_tokens_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS activation_tokens (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                access_type TEXT NULL,
                plan TEXT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                used_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_activation_tokens_email
            ON activation_tokens (email)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_activation_tokens_token
            ON activation_tokens (token)
            """
        )
    )
    # Harmonise la prod si la table existe déjà sans défaut sur created_at
    db.execute(
        text(
            """
            ALTER TABLE activation_tokens
            ALTER COLUMN created_at SET DEFAULT NOW()
            """
        )
    )
    db.flush()


def _create_activation_package(
    db: Session,
    *,
    email: str,
    access_type: str,
    plan: str,
    expires_in_hours: int,
) -> dict:
    clean_email = str(email or "").strip().lower()
    clean_access_type = str(access_type or "").strip().lower()
    clean_plan = str(plan or "").strip().lower()

    if not clean_email:
        raise HTTPException(status_code=400, detail="Missing email")

    _ensure_activation_tokens_table(db)

    db.execute(
        text(
            """
            UPDATE activation_tokens
            SET used = TRUE,
                used_at = NOW()
            WHERE LOWER(email) = LOWER(:email)
              AND COALESCE(access_type, '') = COALESCE(:access_type, '')
              AND used = FALSE
            """
        ),
        {
            "email": clean_email,
            "access_type": clean_access_type,
        },
    )

    token_value = secrets.token_urlsafe(32)
    expires_at = _token_expiration(expires_in_hours)

    row = db.execute(
        text(
            """
            INSERT INTO activation_tokens (
                email,
                token,
                access_type,
                plan,
                expires_at,
                used,
                created_at
            )
            VALUES (
                :email,
                :token,
                :access_type,
                :plan,
                :expires_at,
                FALSE,
                NOW()
            )
            RETURNING token, expires_at, created_at
            """
        ),
        {
            "email": clean_email,
            "token": token_value,
            "access_type": clean_access_type,
            "plan": clean_plan,
            "expires_at": expires_at,
        },
    ).mappings().first()

    activation_url = f"{_frontend_base_url()}/auth/activate?token={row['token']}"

    return {
        "activation_token": row["token"],
        "activation_url": activation_url,
        "token_expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "route_version": ROUTE_VERSION,
        "front_base_used": _frontend_base_url(),
        "db_name": _current_database_name(db),
    }


def _process_event(*, db: Session, event: str, payload: dict) -> dict:
    event = (event or "").upper()

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

        token_bundle = _create_activation_package(
            db=db,
            email=email,
            access_type="trial",
            plan="trial",
            expires_in_hours=24,
        )

        user_id = _get_user_by_email(db, email)
        if user_id:
            sync_plan_quotas(db=db, user_id=int(user_id), plan="trial")
            mark_pending_access_active(db=db, email=email)
            db.commit()
            return {
                "status": "trial_active_existing_user",
                "plan": "trial",
                "email": email,
                "pending": pending,
                **token_bundle,
            }

        db.commit()
        return {
            "status": "trial_pending",
            "email": email,
            "trial_ends_at": pending.get("ends_at"),
            "pending": pending,
            **token_bundle,
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

        token_bundle = _create_activation_package(
            db=db,
            email=email,
            access_type="paid",
            plan=plan,
            expires_in_hours=48,
        )

        if user_id:
            sync_plan_quotas(db=db, user_id=int(user_id), plan=plan)
            mark_pending_access_active(db=db, email=email)
            db.commit()
            return {
                "status": "success_existing_user",
                "email": email,
                "plan": plan,
                "pending": pending,
                **token_bundle,
            }

        db.commit()
        return {
            "status": "paid_pending",
            "email": email,
            "plan": plan,
            "pending": pending,
            **token_bundle,
        }

    if event == "SALE_CANCELED":
        if not user_id:
            return {"status": "ignored", "reason": "user_not_found"}

        sync_plan_quotas(db=db, user_id=int(user_id), plan="essentiel")
        db.commit()
        return {"status": "canceled", "plan": "essentiel"}

    return {"status": "ignored", "event": event}


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
        return _process_event(db=db, event=event, payload=payload)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("❌ WEBHOOK ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def systemeio_webhook_test(data: SystemeioTestPayload, db: Session = Depends(get_db)):
    try:
        return _process_event(db=db, event=data.event, payload=data.payload)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("❌ WEBHOOK TEST ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version")
def systemeio_webhook_version(db: Session = Depends(get_db)):
    return {
        "route_version": ROUTE_VERSION,
        "front_base_used": _frontend_base_url(),
        "db_name": _current_database_name(db),
    }
