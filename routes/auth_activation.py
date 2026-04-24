from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from services.ai_quota_service import sync_plan_quotas
from services.auth_service import (
    _fetch_user_by_identity,
    create_access_token,
    hash_password,
)
from services.pending_access_service import (
    get_pending_access,
    mark_pending_access_active,
)

router = APIRouter(prefix="/auth", tags=["Auth Activation"])


class ConsumeTokenPayload(BaseModel):
    token: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


# ============================================================
# 🔐 Activation tokens — schema guard
# ============================================================
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
    db.execute(
        text(
            """
            ALTER TABLE activation_tokens
            ALTER COLUMN created_at SET DEFAULT NOW()
            """
        )
    )
    db.flush()


def _get_token_metadata(db: Session, token_value: str) -> dict[str, Any] | None:
    _ensure_activation_tokens_table(db)

    clean_token = str(token_value or "").strip()
    if not clean_token:
        return None

    row = db.execute(
        text(
            """
            SELECT id, email, token, access_type, plan, expires_at, used, used_at, created_at
            FROM activation_tokens
            WHERE token = :token
            LIMIT 1
            """
        ),
        {"token": clean_token},
    ).mappings().first()

    return dict(row) if row else None


def _is_token_valid(row: dict[str, Any] | None) -> bool:
    if not row:
        return False

    if bool(row.get("used")):
        return False

    expires_at = row.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at < datetime.utcnow():
        return False

    return True


def _lock_token_for_consumption(db: Session, token_value: str) -> dict[str, Any] | None:
    _ensure_activation_tokens_table(db)

    clean_token = str(token_value or "").strip()
    if not clean_token:
        return None

    row = db.execute(
        text(
            """
            SELECT id, email, token, access_type, plan, expires_at, used, used_at, created_at
            FROM activation_tokens
            WHERE token = :token
            LIMIT 1
            FOR UPDATE
            """
        ),
        {"token": clean_token},
    ).mappings().first()

    token_row = dict(row) if row else None
    if not _is_token_valid(token_row):
        return None

    return token_row


def _mark_token_used(db: Session, token_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE activation_tokens
            SET used = TRUE,
                used_at = NOW()
            WHERE id = :token_id
              AND used = FALSE
            """
        ),
        {"token_id": int(token_id)},
    )
    db.flush()


# ============================================================
# 👤 Users — schema compatible helpers
# ============================================================
def _users_columns(db: Session) -> set[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users'
            """
        )
    ).fetchall()
    return {str(r[0]).lower() for r in rows}


def _password_column(columns: set[str]) -> str:
    for candidate in ("hashed_password", "password_hash", "password"):
        if candidate in columns:
            return candidate
    raise HTTPException(
        status_code=500,
        detail="Aucune colonne mot de passe compatible trouvée dans users.",
    )


def _find_existing_user_id(db: Session, email: str) -> int | None:
    row = db.execute(
        text("SELECT id FROM users WHERE LOWER(email) = LOWER(:email) LIMIT 1"),
        {"email": email},
    ).mappings().first()
    if not row:
        return None
    return int(row["id"])


def _update_existing_user(
    db: Session,
    *,
    user_id: int,
    password: str,
    full_name: str | None,
    plan: str,
) -> int:
    columns = _users_columns(db)
    password_col = _password_column(columns)
    hashed = hash_password(password)

    updates = [f"{password_col} = :password_value"]
    params: dict[str, Any] = {
        "uid": int(user_id),
        "password_value": hashed,
    }

    clean_full_name = str(full_name or "").strip()
    if clean_full_name:
        if "full_name" in columns:
            updates.append("full_name = :full_name")
            params["full_name"] = clean_full_name
        elif "name" in columns:
            updates.append("name = :full_name")
            params["full_name"] = clean_full_name

    if "plan" in columns:
        updates.append("plan = :plan")
        params["plan"] = plan

    if "is_active" in columns:
        updates.append("is_active = TRUE")

    if "updated_at" in columns:
        updates.append("updated_at = NOW()")

    db.execute(
        text(f"UPDATE users SET {', '.join(updates)} WHERE id = :uid"),
        params,
    )
    db.flush()
    return int(user_id)


def _create_new_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str | None,
    plan: str,
) -> int:
    columns = _users_columns(db)
    password_col = _password_column(columns)
    hashed = hash_password(password)

    insert_columns: list[str] = []
    values_sql: list[str] = []
    params: dict[str, Any] = {}

    def add(column: str, placeholder: str, value: Any = None) -> None:
        insert_columns.append(column)
        values_sql.append(placeholder)
        if placeholder.startswith(":"):
            params[placeholder[1:]] = value

    if "email" not in columns:
        raise HTTPException(status_code=500, detail="Colonne email introuvable dans users.")

    add("email", ":email", email)
    add(password_col, ":password_value", hashed)

    clean_full_name = str(full_name or "").strip()
    if clean_full_name:
        if "full_name" in columns:
            add("full_name", ":full_name", clean_full_name)
        elif "name" in columns:
            add("name", ":full_name", clean_full_name)

    if "plan" in columns:
        add("plan", ":plan", plan)

    if "is_active" in columns:
        add("is_active", "TRUE")

    if "created_at" in columns:
        add("created_at", "NOW()")

    if "updated_at" in columns:
        add("updated_at", "NOW()")

    row = db.execute(
        text(
            f"""
            INSERT INTO users ({', '.join(insert_columns)})
            VALUES ({', '.join(values_sql)})
            RETURNING id
            """
        ),
        params,
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=500, detail="Impossible de créer le compte utilisateur.")

    db.flush()
    return int(row["id"])


def _activate_or_sync_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str | None,
    plan: str,
) -> dict[str, Any]:
    existing_user_id = _find_existing_user_id(db, email)

    if existing_user_id:
        user_id = _update_existing_user(
            db=db,
            user_id=existing_user_id,
            password=password,
            full_name=full_name,
            plan=plan,
        )
        existing_user = True
    else:
        user_id = _create_new_user(
            db=db,
            email=email,
            password=password,
            full_name=full_name,
            plan=plan,
        )
        existing_user = False

    sync_plan_quotas(db=db, user_id=int(user_id), plan=plan)
    mark_pending_access_active(db=db, email=email)

    user = _fetch_user_by_identity(db, user_id=user_id, email=email)
    if not user:
        raise HTTPException(status_code=500, detail="Compte créé mais utilisateur introuvable.")

    user["plan"] = user.get("plan") or plan
    user["existing_user"] = existing_user
    return user


# ============================================================
# 🌐 API
# ============================================================
@router.get("/activate-token")
def activate_token(token: str, db: Session = Depends(get_db)):
    record = _get_token_metadata(db, token)
    if not _is_token_valid(record):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide, expiré ou déjà utilisé.",
        )

    pending = get_pending_access(db, email=str(record["email"]))
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès associé introuvable ou expiré.",
        )

    return {
        "valid": True,
        "email": record["email"],
        "access_type": record.get("access_type"),
        "plan": record.get("plan"),
        "expires_at": record["expires_at"].isoformat() if record.get("expires_at") else None,
        "used": bool(record.get("used")),
        "pending": pending,
    }


@router.post("/consume-token")
def consume_token(payload: ConsumeTokenPayload, db: Session = Depends(get_db)):
    try:
        record = _lock_token_for_consumption(db, payload.token)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token invalide, expiré ou déjà utilisé.",
            )

        token_email = str(record["email"] or "").strip().lower()
        payload_email = str(payload.email or "").strip().lower()
        if payload_email and payload_email != token_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ce token ne correspond pas à cet email.",
            )

        pending = get_pending_access(db, email=token_email)
        if not pending:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès associé introuvable ou expiré.",
            )

        plan = str(record.get("plan") or pending.get("plan") or "trial").strip().lower()
        access_type = str(record.get("access_type") or pending.get("access_type") or "trial").strip().lower()

        _mark_token_used(db, int(record["id"]))

        raw_password = str(payload.password or "")
        if not raw_password:
            db.commit()
            return {
                "status": "ok",
                "message": "Token consommé.",
                "email": token_email,
                "access_type": access_type,
                "plan": plan,
                "auto_login": False,
            }

        if len(raw_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le mot de passe doit contenir au moins 6 caractères.",
            )

        user = _activate_or_sync_user(
            db=db,
            email=token_email,
            password=raw_password,
            full_name=payload.full_name or pending.get("full_name"),
            plan=plan,
        )

        access_token = create_access_token(
            {
                "sub": str(user["id"]),
                "email": user["email"],
                "user_id": user["id"],
            }
        )

        db.commit()

        response = JSONResponse(
            {
                "status": "ok",
                "message": "Compte activé et connecté.",
                "token": access_token,
                "access_token": access_token,
                "token_type": "bearer",
                "email": token_email,
                "access_type": access_type,
                "plan": plan,
                "auto_login": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user.get("full_name"),
                    "plan": user.get("plan") or plan,
                    "is_active": user.get("is_active", True),
                    "is_admin": user.get("is_admin", False),
                    "existing_user": user.get("existing_user", False),
                },
            }
        )
        response.set_cookie(
            key="lgd_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=60 * 60 * 24 * 7,
            path="/",
        )
        return response

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print("CONSUME_TOKEN_ERROR:", repr(exc))
        raise HTTPException(status_code=500, detail=str(exc))
