from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_pending_access_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS pending_access (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NULL,
                status TEXT NOT NULL DEFAULT 'trial_pending',
                access_type TEXT NOT NULL DEFAULT 'trial',
                plan TEXT NULL,
                source_event TEXT NULL,
                starts_at TIMESTAMP NULL,
                ends_at TIMESTAMP NULL,
                webhook_payload TEXT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
    )
    db.commit()


def upsert_pending_access(
    db: Session,
    email: str,
    full_name: str | None = None,
    access_type: str = "trial",
    plan: str | None = None,
    source_event: str | None = None,
    payload: dict[str, Any] | None = None,
    duration_days: int | None = 7,
) -> dict[str, Any]:
    ensure_pending_access_table(db)

    clean_email = (email or "").strip().lower()
    clean_access_type = str(access_type or "trial").strip().lower()
    clean_plan = str(plan or ("trial" if clean_access_type == "trial" else "essentiel")).strip().lower()

    now = datetime.utcnow()
    ends_at = now + timedelta(days=duration_days) if duration_days else None
    status = "trial_pending" if clean_access_type == "trial" else "paid_pending"
    payload_text = json.dumps(payload or {}, ensure_ascii=False)

    db.execute(
        text(
            """
            INSERT INTO pending_access (
                email,
                full_name,
                status,
                access_type,
                plan,
                source_event,
                starts_at,
                ends_at,
                webhook_payload,
                updated_at
            )
            VALUES (
                :email,
                :full_name,
                :status,
                :access_type,
                :plan,
                :source_event,
                :starts_at,
                :ends_at,
                :webhook_payload,
                NOW()
            )
            ON CONFLICT (email)
            DO UPDATE SET
                full_name = COALESCE(EXCLUDED.full_name, pending_access.full_name),
                status = EXCLUDED.status,
                access_type = EXCLUDED.access_type,
                plan = EXCLUDED.plan,
                source_event = EXCLUDED.source_event,
                starts_at = EXCLUDED.starts_at,
                ends_at = EXCLUDED.ends_at,
                webhook_payload = EXCLUDED.webhook_payload,
                updated_at = NOW()
            """
        ),
        {
            "email": clean_email,
            "full_name": full_name,
            "status": status,
            "access_type": clean_access_type,
            "plan": clean_plan,
            "source_event": source_event,
            "starts_at": now,
            "ends_at": ends_at,
            "webhook_payload": payload_text,
        },
    )
    db.commit()

    return {
        "email": clean_email,
        "status": status,
        "access_type": clean_access_type,
        "plan": clean_plan,
        "starts_at": now.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
    }


def has_pending_access(db: Session, email: str) -> dict[str, Any]:
    ensure_pending_access_table(db)

    clean_email = (email or "").strip().lower()
    row = db.execute(
        text(
            """
            SELECT email, status, access_type, plan, starts_at, ends_at
            FROM pending_access
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": clean_email},
    ).mappings().first()

    if not row:
        return {
            "email": clean_email,
            "has_access": False,
            "status": None,
            "access_type": None,
            "plan": None,
            "starts_at": None,
            "ends_at": None,
        }

    now = datetime.utcnow()
    ends_at = row.get("ends_at")
    status = str(row.get("status") or "")
    access_type = str(row.get("access_type") or "")

    if access_type == "trial" and ends_at and isinstance(ends_at, datetime) and ends_at < now:
        status = "trial_expired"

    return {
        "email": clean_email,
        "has_access": status in {"trial_pending", "trial_active", "paid_pending", "paid_active"},
        "status": status,
        "access_type": access_type,
        "plan": row.get("plan"),
        "starts_at": row.get("starts_at").isoformat() if row.get("starts_at") else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
    }


def get_pending_access(db: Session, email: str) -> dict[str, Any] | None:
    ensure_pending_access_table(db)

    clean_email = (email or "").strip().lower()
    row = db.execute(
        text(
            """
            SELECT id, email, full_name, status, access_type, plan, starts_at, ends_at
            FROM pending_access
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": clean_email},
    ).mappings().first()

    if not row:
        return None

    now = datetime.utcnow()
    ends_at = row.get("ends_at")
    status = str(row.get("status") or "")
    access_type = str(row.get("access_type") or "")
    plan = str(row.get("plan") or "")

    if access_type == "trial" and ends_at and isinstance(ends_at, datetime) and ends_at < now:
        db.execute(
            text(
                """
                UPDATE pending_access
                SET status = 'trial_expired', updated_at = NOW()
                WHERE email = :email
                """
            ),
            {"email": clean_email},
        )
        db.commit()
        return None

    if status not in {"trial_pending", "trial_active", "paid_pending", "paid_active"}:
        return None

    return {
        "email": clean_email,
        "full_name": row.get("full_name"),
        "status": status,
        "access_type": access_type,
        "plan": plan,
        "starts_at": row.get("starts_at").isoformat() if row.get("starts_at") else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
    }


def mark_pending_access_active(db: Session, email: str) -> dict[str, Any] | None:
    current = get_pending_access(db, email)
    if not current:
        return None

    clean_email = (email or "").strip().lower()
    next_status = "trial_active" if current.get("access_type") == "trial" else "paid_active"

    db.execute(
        text(
            """
            UPDATE pending_access
            SET status = :status, updated_at = NOW()
            WHERE email = :email
            """
        ),
        {"email": clean_email, "status": next_status},
    )
    db.flush()

    current["status"] = next_status
    return current


# backward compatibility
def consume_pending_access(db: Session, email: str) -> dict[str, Any] | None:
    current = get_pending_access(db, email)
    if not current:
        return None
    return mark_pending_access_active(db, email)
