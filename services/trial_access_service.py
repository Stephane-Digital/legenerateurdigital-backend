from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_trial_access_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS trial_access (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NULL,
                status TEXT NOT NULL DEFAULT 'trial_pending',
                source_event TEXT NULL,
                trial_starts_at TIMESTAMP NULL,
                trial_ends_at TIMESTAMP NULL,
                webhook_payload TEXT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
    )
    db.commit()


def upsert_trial_pending(
    db: Session,
    email: str,
    full_name: str | None = None,
    source_event: str | None = None,
    payload: dict[str, Any] | None = None,
    duration_days: int = 7,
) -> dict[str, Any]:
    ensure_trial_access_table(db)

    clean_email = (email or "").strip().lower()
    now = datetime.utcnow()
    ends_at = now + timedelta(days=duration_days)
    payload_text = json.dumps(payload or {}, ensure_ascii=False)

    db.execute(
        text(
            """
            INSERT INTO trial_access (
                email,
                full_name,
                status,
                source_event,
                trial_starts_at,
                trial_ends_at,
                webhook_payload,
                updated_at
            )
            VALUES (
                :email,
                :full_name,
                'trial_pending',
                :source_event,
                :trial_starts_at,
                :trial_ends_at,
                :webhook_payload,
                NOW()
            )
            ON CONFLICT (email)
            DO UPDATE SET
                full_name = COALESCE(EXCLUDED.full_name, trial_access.full_name),
                status = 'trial_pending',
                source_event = EXCLUDED.source_event,
                trial_starts_at = EXCLUDED.trial_starts_at,
                trial_ends_at = EXCLUDED.trial_ends_at,
                webhook_payload = EXCLUDED.webhook_payload,
                updated_at = NOW()
            """
        ),
        {
            "email": clean_email,
            "full_name": full_name,
            "source_event": source_event,
            "trial_starts_at": now,
            "trial_ends_at": ends_at,
            "webhook_payload": payload_text,
        },
    )
    db.commit()

    return {
        "email": clean_email,
        "status": "trial_pending",
        "trial_starts_at": now.isoformat(),
        "trial_ends_at": ends_at.isoformat(),
    }


def has_trial_access(db: Session, email: str) -> dict[str, Any]:
    ensure_trial_access_table(db)

    clean_email = (email or "").strip().lower()
    row = db.execute(
        text(
            """
            SELECT email, status, trial_starts_at, trial_ends_at
            FROM trial_access
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
            "trial_starts_at": None,
            "trial_ends_at": None,
        }

    now = datetime.utcnow()
    trial_ends_at = row.get("trial_ends_at")
    status = str(row.get("status") or "trial_pending")

    if trial_ends_at and isinstance(trial_ends_at, datetime) and trial_ends_at < now:
        status = "trial_expired"

    return {
        "email": clean_email,
        "has_access": status in {"trial_pending", "trial_active"},
        "status": status,
        "trial_starts_at": row.get("trial_starts_at").isoformat() if row.get("trial_starts_at") else None,
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
    }


def consume_trial_pending(db: Session, email: str) -> dict[str, Any] | None:
    ensure_trial_access_table(db)

    clean_email = (email or "").strip().lower()
    row = db.execute(
        text(
            """
            SELECT id, email, status, trial_starts_at, trial_ends_at
            FROM trial_access
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": clean_email},
    ).mappings().first()

    if not row:
        return None

    now = datetime.utcnow()
    trial_ends_at = row.get("trial_ends_at")
    status = str(row.get("status") or "trial_pending")

    if trial_ends_at and isinstance(trial_ends_at, datetime) and trial_ends_at < now:
        db.execute(
            text(
                """
                UPDATE trial_access
                SET status = 'trial_expired', updated_at = NOW()
                WHERE email = :email
                """
            ),
            {"email": clean_email},
        )
        db.commit()
        return None

    if status not in {"trial_pending", "trial_active"}:
        return None

    db.execute(
        text(
            """
            UPDATE trial_access
            SET status = 'trial_active', updated_at = NOW()
            WHERE email = :email
            """
        ),
        {"email": clean_email},
    )
    db.commit()

    return {
        "email": clean_email,
        "status": "trial_active",
        "trial_starts_at": row.get("trial_starts_at").isoformat() if row.get("trial_starts_at") else None,
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
    }
