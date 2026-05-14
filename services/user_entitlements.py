from __future__ import annotations

"""LGD — User entitlements / temporary commercial upgrades.

But métier : séparer le plan réel payé via Systeme.io du bonus commercial temporaire.

- base_plan = plan réel SIO / essai d'origine (azur, essentiel, pro, ultime)
- override_plan = bonus temporaire admin (ex : pro 3 mois / ultime 3 mois)
- effective_plan = override actif si présent, sinon base_plan

Ce fichier reste volontairement ORM-free et compatible avec le schéma existant.
Important prod : la table users ne contient PAS de colonne plan. La vérité du plan
vient donc uniquement de user_plan_state + user_entitlements.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

TABLE = "user_entitlements"
STATE_TABLE = "user_plan_state"

PLAN_ALIASES = {
    "trial": "azur",
    "azur": "azur",
    "starter": "azur",
    "decouverte": "azur",
    "découverte": "azur",
    "free": "azur",
    "essential": "essentiel",
    "essentiel": "essentiel",
    "essentiels": "essentiel",
    "pro": "pro",
    "professional": "pro",
    "ultimate": "ultime",
    "ultime": "ultime",
    "premium": "ultime",
}

PLAN_LABELS = {
    "azur": "Azur / essai",
    "essentiel": "Essentiel",
    "pro": "Pro",
    "ultime": "Ultime",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm_plan(plan: Optional[str]) -> str:
    p = (plan or "").strip().lower()
    return PLAN_ALIASES.get(p, "essentiel")


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return str(value)
    except Exception:
        return None


def _days_remaining(ends_at: Any) -> Optional[int]:
    if not ends_at:
        return None
    try:
        end = ends_at
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if getattr(end, "tzinfo", None) is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - _utcnow()
        if delta.total_seconds() <= 0:
            return 0
        return max(1, int((delta.total_seconds() + 86399) // 86400))
    except Exception:
        return None


def ensure_table(db: Session) -> None:
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
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL UNIQUE,
              base_plan VARCHAR(32) NOT NULL DEFAULT 'essentiel',
              source VARCHAR(120) NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_{STATE_TABLE}_user_id ON {STATE_TABLE}(user_id);
            """
        )
    )
    db.flush()


def _user_table_plan(db: Session, user_id: int) -> Optional[str]:
    """LGD SAFE: users.plan n'existe pas en prod. Ne jamais SELECT dessus."""
    return None


def get_base_plan(db: Session, *, user_id: int, fallback: Optional[str] = None) -> str:
    ensure_table(db)
    row = db.execute(
        text(
            f"""
            SELECT base_plan
            FROM {STATE_TABLE}
            WHERE user_id = :uid
            LIMIT 1
            """
        ),
        {"uid": int(user_id)},
    ).mappings().first()
    if row and row.get("base_plan"):
        return _norm_plan(str(row["base_plan"]))

    user_plan = _user_table_plan(db, int(user_id))
    if user_plan:
        return user_plan

    return _norm_plan(fallback)


def set_base_plan(
    db: Session,
    *,
    user_id: int,
    base_plan: str,
    source: Optional[str] = None,
    sync_user_column: bool = False,
) -> Dict[str, Any]:
    """Enregistre le plan réel payé / essai sans toucher au bonus temporaire actif.

    Important : on ne synchronise pas users.plan, car cette colonne n'existe pas
    dans la base Render/pgAdmin actuelle. Le paramètre sync_user_column reste
    présent seulement pour compatibilité de signature.
    """
    ensure_table(db)
    plan = _norm_plan(base_plan)
    db.execute(
        text(
            f"""
            INSERT INTO {STATE_TABLE}(user_id, base_plan, source, created_at, updated_at)
            VALUES (:uid, :plan, :source, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET base_plan = EXCLUDED.base_plan,
                          source = EXCLUDED.source,
                          updated_at = NOW()
            """
        ),
        {"uid": int(user_id), "plan": plan, "source": source},
    )
    db.flush()
    return {"ok": True, "user_id": int(user_id), "base_plan": plan, "source": source}


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
    if not row:
        return None
    data = dict(row)
    data["override_plan"] = _norm_plan(str(data.get("override_plan") or ""))
    data["temporary_plan"] = data["override_plan"]
    data["temporary_until"] = data.get("ends_at")
    data["temporary_days_remaining"] = _days_remaining(data.get("ends_at"))
    data["starts_at_iso"] = _iso(data.get("starts_at"))
    data["ends_at_iso"] = _iso(data.get("ends_at"))
    return data


def get_plan_state(db: Session, *, user_id: int, base_plan: Optional[str] = None) -> Dict[str, Any]:
    base = get_base_plan(db, user_id=int(user_id), fallback=base_plan)
    ov = get_active_override(db, int(user_id))
    effective = _norm_plan(ov.get("override_plan")) if ov else base
    return {
        "user_id": int(user_id),
        "base_plan": base,
        "base_plan_label": PLAN_LABELS.get(base, base),
        "effective_plan": effective,
        "effective_plan_label": PLAN_LABELS.get(effective, effective),
        "temporary_plan": ov.get("override_plan") if ov else None,
        "temporary_plan_label": PLAN_LABELS.get(ov.get("override_plan"), ov.get("override_plan")) if ov else None,
        "temporary_until": _iso(ov.get("ends_at")) if ov else None,
        "temporary_days_remaining": ov.get("temporary_days_remaining") if ov else None,
        "temporary_active": bool(ov),
        "override": ov,
    }


def get_effective_plan(db: Session, *, user_id: int, base_plan: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    state = get_plan_state(db, user_id=int(user_id), base_plan=base_plan)
    ov = state.get("override") if state.get("temporary_active") else None
    return _norm_plan(str(state.get("effective_plan") or base_plan)), ov


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
    if p not in {"pro", "ultime", "essentiel", "azur"}:
        raise ValueError("plan invalide")

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
    db.flush()
    return get_plan_state(db, user_id=int(user_id))


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
    db.flush()
    return get_plan_state(db, user_id=int(user_id))


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
