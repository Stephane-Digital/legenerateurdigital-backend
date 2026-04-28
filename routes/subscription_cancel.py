from datetime import datetime
import html
import os
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/subscription", tags=["Subscription"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

# On réutilise les variables déjà présentes en production Render.
FROM_EMAIL = os.getenv(
    "LGD_ACTIVATION_FROM_EMAIL",
    "Le Générateur Digital <no-reply@legenerateurdigital.com>",
).strip()

ADMIN_EMAIL = os.getenv(
    "LGD_SUPPORT_EMAIL",
    "contact@legenerateurdigital.com",
).strip()


def _get_user_value(user: Any, key: str, default: str = "") -> str:
    if isinstance(user, dict):
        value = user.get(key, default)
    else:
        value = getattr(user, key, default)

    if value is None:
        return default

    return str(value).strip()


def _get_first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            return clean
    return default


def _table_exists(db: Session, table_name: str) -> bool:
    try:
        row = db.execute(
            text("SELECT to_regclass(:table_name) AS table_name"),
            {"table_name": table_name},
        ).mappings().first()
        return bool(row and row.get("table_name"))
    except Exception:
        return False


def _table_columns(db: Session, table_name: str) -> set[str]:
    try:
        rows = db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()
        return {str(row[0]).lower() for row in rows}
    except Exception:
        return set()


def _fetch_user_profile_from_db(db: Session, email: str) -> dict[str, Any]:
    clean_email = str(email or "").strip().lower()
    if not clean_email or not _table_exists(db, "users"):
        return {}

    columns = _table_columns(db, "users")
    select_parts = ["email"]

    for candidate in ("full_name", "name", "plan", "is_active"):
        if candidate in columns:
            select_parts.append(candidate)

    try:
        row = db.execute(
            text(
                f"""
                SELECT {", ".join(select_parts)}
                FROM users
                WHERE LOWER(email) = LOWER(:email)
                LIMIT 1
                """
            ),
            {"email": clean_email},
        ).mappings().first()
        return dict(row) if row else {}
    except Exception:
        return {}


def _fetch_pending_access_from_db(db: Session, email: str) -> dict[str, Any]:
    clean_email = str(email or "").strip().lower()
    if not clean_email or not _table_exists(db, "pending_access"):
        return {}

    columns = _table_columns(db, "pending_access")
    select_parts = []

    for candidate in (
        "email",
        "full_name",
        "access_type",
        "plan",
        "status",
        "ends_at",
        "expires_at",
        "created_at",
        "updated_at",
    ):
        if candidate in columns:
            select_parts.append(candidate)

    if not select_parts:
        return {}

    order_column = "updated_at" if "updated_at" in columns else "created_at" if "created_at" in columns else "email"

    try:
        row = db.execute(
            text(
                f"""
                SELECT {", ".join(select_parts)}
                FROM pending_access
                WHERE LOWER(email) = LOWER(:email)
                ORDER BY {order_column} DESC
                LIMIT 1
                """
            ),
            {"email": clean_email},
        ).mappings().first()
        return dict(row) if row else {}
    except Exception:
        return {}


def _fetch_quota_plan_from_db(db: Session, email: str) -> str:
    clean_email = str(email or "").strip().lower()
    if not clean_email:
        return ""

    possible_tables = ("ia_quotas", "ai_quotas", "user_ai_quotas")

    for table_name in possible_tables:
        if not _table_exists(db, table_name):
            continue

        columns = _table_columns(db, table_name)
        if "plan" not in columns:
            continue

        try:
            if "email" in columns:
                row = db.execute(
                    text(
                        f"""
                        SELECT plan
                        FROM {table_name}
                        WHERE LOWER(email) = LOWER(:email)
                        LIMIT 1
                        """
                    ),
                    {"email": clean_email},
                ).mappings().first()
                if row and row.get("plan"):
                    return str(row["plan"]).strip()

            if "user_id" in columns and _table_exists(db, "users"):
                row = db.execute(
                    text(
                        f"""
                        SELECT q.plan
                        FROM {table_name} q
                        JOIN users u ON u.id = q.user_id
                        WHERE LOWER(u.email) = LOWER(:email)
                        LIMIT 1
                        """
                    ),
                    {"email": clean_email},
                ).mappings().first()
                if row and row.get("plan"):
                    return str(row["plan"]).strip()
        except Exception:
            continue

    return ""


def _normalize_plan_label(*, current_plan: str, pending: dict[str, Any], quota_plan: str) -> str:
    pending_access_type = str(pending.get("access_type") or "").strip().lower()
    pending_plan = str(pending.get("plan") or "").strip().lower()
    quota_clean = str(quota_plan or "").strip().lower()
    current_clean = str(current_plan or "").strip().lower()

    # Priorité au pending_access : c'est la source la plus fiable pour l'essai SIO.
    if pending_access_type == "trial" or pending_plan == "trial":
        return "Essai gratuit 7 jours"

    if quota_clean in {"trial", "essai", "essai_7j", "essai_7_jours"}:
        return "Essai gratuit 7 jours"

    if current_clean in {"trial", "essai", "essai_7j", "essai_7_jours"}:
        return "Essai gratuit 7 jours"

    labels = {
        "essentiel": "Essentiel",
        "essential": "Essentiel",
        "pro": "Pro",
        "ultime": "Ultime",
        "ultimate": "Ultime",
        "azur": "Azur",
    }

    if pending_plan in labels:
        return labels[pending_plan]

    if quota_clean in labels:
        return labels[quota_clean]

    if current_clean in labels:
        return labels[current_clean]

    return _get_first_non_empty(pending_plan, quota_clean, current_clean, default="Inconnu")


def _send_resend_email(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    reply_to: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }

    if reply_to:
        payload["reply_to"] = reply_to

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur réseau Resend: {str(exc)}",
        )

    response_text = response.text or ""

    try:
        response_json = response.json()
    except ValueError:
        response_json = {}

    if response.status_code not in (200, 202):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Resend a refusé l'envoi de l'email.",
                "resend_status": response.status_code,
                "resend_body": response_text,
                "from": FROM_EMAIL,
                "to": to_email,
            },
        )

    return {
        "status": response.status_code,
        "id": response_json.get("id") if isinstance(response_json, dict) else None,
        "to": to_email,
    }


@router.post("/cancel-request")
def cancel_subscription_request(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    user_email = _get_user_value(current_user, "email", "")
    if not user_email:
        raise HTTPException(
            status_code=400,
            detail="Impossible de récupérer l'adresse email de l'utilisateur connecté.",
        )

    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="RESEND_API_KEY manquant côté serveur Render.",
        )

    if not FROM_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="LGD_ACTIVATION_FROM_EMAIL manquant côté serveur Render.",
        )

    if not ADMIN_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="LGD_SUPPORT_EMAIL manquant côté serveur Render.",
        )

    db_user = _fetch_user_profile_from_db(db, user_email)
    pending_access = _fetch_pending_access_from_db(db, user_email)
    quota_plan = _fetch_quota_plan_from_db(db, user_email)

    current_user_name = _get_first_non_empty(
        _get_user_value(current_user, "full_name", ""),
        _get_user_value(current_user, "name", ""),
        _get_user_value(current_user, "username", ""),
    )

    user_name = _get_first_non_empty(
        pending_access.get("full_name"),
        db_user.get("full_name"),
        db_user.get("name"),
        current_user_name,
        user_email.split("@")[0],
        default="Utilisateur LGD",
    )

    current_plan = _get_first_non_empty(
        _get_user_value(current_user, "plan", ""),
        db_user.get("plan"),
        default="",
    )

    user_plan = _normalize_plan_label(
        current_plan=current_plan,
        pending=pending_access,
        quota_plan=quota_plan,
    )

    safe_user_name = html.escape(user_name)
    safe_user_email = html.escape(user_email)
    safe_user_plan = html.escape(user_plan)
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    admin_html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;padding:20px;color:#111;line-height:1.6;">
      <h2 style="margin:0 0 16px;">Demande de résiliation LGD</h2>
      <p><strong>Nom :</strong> {safe_user_name}</p>
      <p><strong>Email utilisateur :</strong> {safe_user_email}</p>
      <p><strong>Plan / accès actuel :</strong> {safe_user_plan}</p>
      <p><strong>Date de demande :</strong> {now}</p>
      <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;" />
      <p>
        Cette demande a été envoyée automatiquement depuis le bouton
        “Se désabonner” du dashboard LGD.
      </p>
      <p>
        Action à effectuer : vérifier le compte utilisateur et résilier manuellement l'abonnement correspondant dans Systeme.io si nécessaire.
      </p>
    </div>
    """

    admin_text = (
        "Demande de résiliation LGD\n\n"
        f"Nom : {user_name}\n"
        f"Email utilisateur : {user_email}\n"
        f"Plan / accès actuel : {user_plan}\n"
        f"Date de demande : {now}\n\n"
        "Action à effectuer : vérifier le compte utilisateur et résilier manuellement l'abonnement correspondant dans Systeme.io si nécessaire."
    )

    user_html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;padding:20px;color:#111;line-height:1.6;">
      <h2 style="margin:0 0 16px;">Votre demande de résiliation a bien été reçue</h2>
      <p>Bonjour {safe_user_name},</p>
      <p>
        Nous confirmons la bonne réception de votre demande de résiliation pour votre accès
        <strong>Le Générateur Digital</strong>.
      </p>
      <p><strong>Email du compte :</strong> {safe_user_email}</p>
      <p><strong>Plan / accès actuel :</strong> {safe_user_plan}</p>
      <p><strong>Date de demande :</strong> {now}</p>
      <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;" />
      <p>
        Votre demande sera traitée manuellement dans les meilleurs délais.
        Votre accès reste actif jusqu'au traitement effectif de la résiliation ou jusqu'à la fin de la période déjà réglée,
        selon les conditions applicables.
      </p>
      <p>
        Pour toute question, vous pouvez répondre directement à cet email.
      </p>
      <p style="margin-top:24px;">
        L'équipe Le Générateur Digital
      </p>
    </div>
    """

    user_text = (
        "Votre demande de résiliation a bien été reçue\n\n"
        f"Bonjour {user_name},\n\n"
        "Nous confirmons la bonne réception de votre demande de résiliation pour votre accès Le Générateur Digital.\n\n"
        f"Email du compte : {user_email}\n"
        f"Plan / accès actuel : {user_plan}\n"
        f"Date de demande : {now}\n\n"
        "Votre demande sera traitée manuellement dans les meilleurs délais. "
        "Votre accès reste actif jusqu'au traitement effectif de la résiliation ou jusqu'à la fin de la période déjà réglée, "
        "selon les conditions applicables.\n\n"
        "Pour toute question, vous pouvez répondre directement à cet email.\n\n"
        "L'équipe Le Générateur Digital"
    )

    admin_result = _send_resend_email(
        to_email=ADMIN_EMAIL,
        reply_to=user_email,
        subject="Demande de résiliation abonnement LGD",
        html_content=admin_html,
        text_content=admin_text,
    )

    user_result = _send_resend_email(
        to_email=user_email,
        reply_to=ADMIN_EMAIL,
        subject="Confirmation de votre demande de résiliation LGD",
        html_content=user_html,
        text_content=user_text,
    )

    return {
        "success": True,
        "message": "Demande de résiliation envoyée à LGD et confirmation envoyée à l'utilisateur.",
        "admin_email": {
            "resend_status": admin_result["status"],
            "resend_id": admin_result["id"],
            "to": admin_result["to"],
        },
        "user_email": {
            "resend_status": user_result["status"],
            "resend_id": user_result["id"],
            "to": user_result["to"],
        },
        "from": FROM_EMAIL,
        "resolved_user": {
            "email": user_email,
            "name": user_name,
            "plan": user_plan,
        },
    }
