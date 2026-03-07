from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/social-accounts", tags=["Social Accounts"])


# =============================
# Helpers DB-safe
# =============================
_SOCIAL_ACCOUNTS_COLS_CACHE: Optional[Set[str]] = None


def _get_social_accounts_cols(db: Session) -> Set[str]:
    global _SOCIAL_ACCOUNTS_COLS_CACHE
    if _SOCIAL_ACCOUNTS_COLS_CACHE is not None:
        return _SOCIAL_ACCOUNTS_COLS_CACHE

    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'social_accounts'
            """
        )
    ).fetchall()
    cols = {r[0] for r in rows}
    _SOCIAL_ACCOUNTS_COLS_CACHE = cols
    return cols


def _mask_token(tok: Optional[str]) -> Optional[str]:
    if not tok:
        return None
    t = str(tok)
    if len(t) <= 10:
        return "***"
    return t[:4] + "..." + t[-4:]


def _row_to_public(row: Dict, cols: Set[str]) -> Dict:
    # Return only useful + safe fields (no full tokens by default)
    out: Dict = {
        "id": row.get("id"),
        "provider": row.get("provider"),
        "user_id": row.get("user_id"),
    }

    if "created_at" in cols:
        out["created_at"] = row.get("created_at")
    if "updated_at" in cols:
        out["updated_at"] = row.get("updated_at")

    if "expires_in" in cols:
        out["expires_in"] = row.get("expires_in")
    if "expires_at" in cols:
        out["expires_at"] = row.get("expires_at")

    # Provide masked tokens for debug
    if "access_token" in cols:
        out["access_token"] = _mask_token(row.get("access_token"))
    if "refresh_token" in cols:
        out["refresh_token"] = _mask_token(row.get("refresh_token"))

    return out


# ============================================================
# 🟢 GET — comptes sociaux de l'utilisateur (safe)
# ============================================================
@router.get("/")
def list_my_accounts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    cols = _get_social_accounts_cols(db)

    required = {"id", "user_id", "provider"}
    if not required.issubset(cols):
        raise HTTPException(
            status_code=500,
            detail=f"social_accounts schema missing required columns: {sorted(list(required - cols))}",
        )

    select_cols = ["id", "user_id", "provider"]
    for opt in [
        "access_token",
        "refresh_token",
        "expires_in",
        "expires_at",
        "created_at",
        "updated_at",
    ]:
        if opt in cols:
            select_cols.append(opt)

    sql = f"""
        SELECT {', '.join(select_cols)}
        FROM social_accounts
        WHERE user_id = :user_id
        ORDER BY id DESC
    """

    rows = (
        db.execute(text(sql), {"user_id": user.id})
        .mappings()
        .all()
    )

    return [_row_to_public(dict(r), cols) for r in rows]


# ============================================================
# 🔴 DELETE — déconnecter un provider
# ============================================================
@router.delete("/{provider}")
def disconnect_provider(
    provider: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    provider = (provider or "").strip().lower()

    cols = _get_social_accounts_cols(db)
    required = {"id", "user_id", "provider"}
    if not required.issubset(cols):
        raise HTTPException(
            status_code=500,
            detail=f"social_accounts schema missing required columns: {sorted(list(required - cols))}",
        )

    existing = db.execute(
        text(
            """
            SELECT id
            FROM social_accounts
            WHERE user_id = :user_id AND provider = :provider
            LIMIT 1
            """
        ),
        {"user_id": user.id, "provider": provider},
    ).mappings().first()

    if not existing:
        raise HTTPException(status_code=404, detail="Compte non trouvé")

    db.execute(text("DELETE FROM social_accounts WHERE id = :id"), {"id": existing["id"]})
    db.commit()

    return {"status": "disconnected", "provider": provider, "user_id": user.id}


# ============================================================
# 🟡 POST — debug/manual upsert (optionnel)
#     (utile si tu veux connecter sans OAuth pendant dev)
# ============================================================
@router.post("/")
def upsert_manual(
    payload: Dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Payload attendu:
    {
      "provider": "facebook",
      "access_token": "...",
      "refresh_token": null,
      "expires_in": 3600
    }

    ⚠️ Tokens stockés en DB. Utiliser uniquement en dev.
    """

    provider = (payload.get("provider") or "").strip().lower()
    if provider not in {"instagram", "facebook", "linkedin", "tiktok"}:
        raise HTTPException(status_code=400, detail="Provider non supporté")

    cols = _get_social_accounts_cols(db)
    required = {"user_id", "provider", "access_token"}
    if not required.issubset(cols):
        raise HTTPException(
            status_code=500,
            detail=f"social_accounts schema missing required columns: {sorted(list(required - cols))}",
        )

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")

    existing = db.execute(
        text(
            """
            SELECT id
            FROM social_accounts
            WHERE user_id = :user_id AND provider = :provider
            LIMIT 1
            """
        ),
        {"user_id": user.id, "provider": provider},
    ).mappings().first()

    fields: Dict[str, object] = {
        "user_id": user.id,
        "provider": provider,
        "access_token": access_token,
    }

    if "refresh_token" in cols:
        fields["refresh_token"] = refresh_token

    if "expires_in" in cols:
        fields["expires_in"] = expires_in
    if "expires_at" in cols:
        try:
            if expires_in:
                fields["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))  # type: ignore
            else:
                fields["expires_at"] = None
        except Exception:
            fields["expires_at"] = None

    now_utc = datetime.now(timezone.utc)
    if "updated_at" in cols:
        fields["updated_at"] = now_utc
    if "created_at" in cols and not existing:
        fields["created_at"] = now_utc

    if existing:
        set_parts = []
        params = {"id": existing["id"]}
        for k, v in fields.items():
            if k in ("user_id", "provider"):
                continue
            if k in cols:
                set_parts.append(f"{k} = :{k}")
                params[k] = v
        db.execute(text(f"UPDATE social_accounts SET {', '.join(set_parts)} WHERE id = :id"), params)
        db.commit()
        return {"status": "updated", "provider": provider}

    insert_cols = []
    insert_vals = []
    params = {}
    for k, v in fields.items():
        if k in cols:
            insert_cols.append(k)
            insert_vals.append(f":{k}")
            params[k] = v

    db.execute(
        text(f"INSERT INTO social_accounts ({', '.join(insert_cols)}) VALUES ({', '.join(insert_vals)})"),
        params,
    )
    db.commit()

    return {"status": "created", "provider": provider}
