from __future__ import annotations

"""User entitlements (plan override) for LGD.

We keep this module **ORM-free** and compatible with existing DB schema:

Table: user_entitlements
Columns (expected):
- id (bigserial)
- user_id (bigint)
- override_plan (varchar)
- starts_at (timestamptz)
- ends_at (timestamptz)
- note (text, nullable)
- created_by (varchar, nullable)
- created_at (timestamptz, default now)

This module exposes backward-compatible helpers used by admin routes and quota services:
- _norm_plan(plan) -> 'essentiel'|'pro'|'ultime'
- get_active_override(db, user_id)
- get_effective_plan(db, user_id, base_plan=None)
- set_plan_override(db, user_id, plan, months=3, note=None, created_by=None)
- clear_plan_override(db, user_id)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

TABLE = "user_entitlements"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm_plan(plan: Optional[str]) -> str:
    p = (plan or "").strip().lower()
    if p in {"essential", "essentiel", "essentiels"}:
        return "essentiel"
    if p in {"pro", "professional"}:
        return "pro"
    if p in {"ultimate", "ultime"}:
        return "ultime"
    # default safe
    return "essentiel"


def ensure_table(db: Session) -> None:
    # PostgreSQL-safe CREATE TABLE IF NOT EXISTS (no ORM dependency)
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              override_plan VARCHAR(32) NOT NULL,
              starts_at TIMESTAMPTZ NOT NULL,
              ends_at TIMESTAMPTZ NOT NULL,
              note TEXT NULL,
              created_by VARCHAR(255) NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_{TABLE}_user_id ON {TABLE}(user_id);
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_active ON {TABLE}(user_id, starts_at, ends_at);
            """
        )
    )
    db.commit()


def get_active_override(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    ensure_table(db)
    now = _utcnow()
    row = (
        db.execute(
            text(
                f"""
                SELECT id, user_id, override_plan, starts_at, ends_at, note, created_by, created_at
                FROM {TABLE}
                WHERE user_id = :uid
                  AND starts_at <= :now
                  AND ends_at > :now
                ORDER BY ends_at DESC
                LIMIT 1
                """
            ),
            {"uid": int(user_id), "now": now},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_effective_plan(db: Session, *, user_id: int, base_plan: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Return (effective_plan, override_row_or_none)."""
    ov = get_active_override(db, int(user_id))
    if ov and ov.get("override_plan"):
        return _norm_plan(str(ov["override_plan"])), ov
    return _norm_plan(base_plan), None


def set_plan_override(
    db: Session,
    *,
    user_id: int,
    plan: str,
    months: int = 3,
    note: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_table(db)

    p = _norm_plan(plan)
    months = int(months or 3)
    if months < 1 or months > 36:
        raise ValueError("months must be between 1 and 36")

    now = _utcnow()
    ends = now + timedelta(days=30 * months)

    db.execute(
        text(
            f"""
            INSERT INTO {TABLE}(user_id, override_plan, starts_at, ends_at, note, created_by)
            VALUES (:uid, :plan, :starts, :ends, :note, :created_by)
            """
        ),
        {"uid": int(user_id), "plan": p, "starts": now, "ends": ends, "note": note, "created_by": created_by},
    )
    db.commit()
    return get_active_override(db, int(user_id)) or {"ok": True}


def clear_plan_override(db: Session, *, user_id: int) -> Dict[str, Any]:
    ensure_table(db)
    now = _utcnow()
    db.execute(
        text(
            f"""
            UPDATE {TABLE}
            SET ends_at = :now
            WHERE user_id = :uid
              AND starts_at <= :now
              AND ends_at > :now
            """
        ),
        {"uid": int(user_id), "now": now},
    )
    db.commit()
    return {"ok": True}


# Backward-compatible aliases (older patches used these names)
def set_override(
    db: Session,
    *,
    user_id: int,
    override_plan: str,
    months: int = 3,
    note: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    return set_plan_override(db, user_id=int(user_id), plan=override_plan, months=months, note=note, created_by=created_by)


def clear_override(db: Session, *, user_id: int) -> Dict[str, Any]:
    return clear_plan_override(db, user_id=int(user_id))
