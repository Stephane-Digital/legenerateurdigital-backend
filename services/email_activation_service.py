from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from html import escape
from typing import Any


DEFAULT_FROM_EMAIL = "Le Générateur Digital <contact@legenerateurdigital.fr>"
RESEND_API_URL = "https://api.resend.com/emails"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default or "").strip()


def _from_email() -> str:
    return (
        _env("LGD_ACTIVATION_FROM_EMAIL")
        or _env("RESEND_FROM_EMAIL")
        or _env("MAIL_FROM")
        or DEFAULT_FROM_EMAIL
    )


def _reply_to() -> str | None:
    value = _env("LGD_SUPPORT_EMAIL") or _env("RESEND_REPLY_TO")
    return value or None


def _display_plan(access_type: str, plan: str) -> str:
    clean_access = (access_type or "").strip().lower()
    clean_plan = (plan or "").strip().lower()

    if clean_access == "trial" or clean_plan == "trial":
        return "Essai gratuit 7 jours"
    if clean_plan == "ultime":
        return "Plan Ultime"
    if clean_plan == "pro":
        return "Plan Pro"
    if clean_plan == "essentiel":
        return "Plan Essentiel"
    return "Accès LGD"


def _subject(access_type: str, plan: str, expires_in_hours: int) -> str:
    label = _display_plan(access_type, plan)
    return f"🚀 Active ton accès LGD — {label} valable {expires_in_hours}h"


def _text_body(
    *,
    full_name: str | None,
    access_type: str,
    plan: str,
    activation_url: str,
    expires_in_hours: int,
) -> str:
    name = (full_name or "").strip()
    hello = f"Bonjour {name}," if name else "Bonjour,"
    label = _display_plan(access_type, plan)

    return f"""{hello}

Ton accès à Le Générateur Digital est prêt.

Accès concerné : {label}

Pour finaliser ton compte, clique sur ce lien sécurisé :
{activation_url}

Important :
- Ce lien est valable {expires_in_hours} heures.
- Ce lien est utilisable une seule fois.
- Après activation, il sera automatiquement désactivé pour ta sécurité.

Après activation, tu pourras accéder à :
- ton Dashboard LGD,
- Alex IA Digital Coach,
- l'Éditeur Intelligent,
- Emailing IA,
- Lead Engine IA.

Si le lien a expiré ou a déjà été utilisé, retourne sur la page d'activation pour demander un nouveau lien.

À très vite dans LGD,
L'équipe Le Générateur Digital
"""


def _html_body(
    *,
    full_name: str | None,
    access_type: str,
    plan: str,
    activation_url: str,
    expires_in_hours: int,
) -> str:
    name = escape((full_name or "").strip())
    label = escape(_display_plan(access_type, plan))
    safe_url = escape(activation_url, quote=True)
    hello = f"Bonjour {name}," if name else "Bonjour,"

    return f"""<!doctype html>
<html lang="fr">
  <body style="margin:0;padding:0;background:#050505;color:#ffffff;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#050505;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:linear-gradient(180deg,#111111,#070707);border:1px solid rgba(255,190,40,.22);border-radius:22px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.55);">
            <tr>
              <td style="padding:34px 30px 10px 30px;text-align:center;">
                <div style="font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:#f6c400;font-weight:700;">Le Générateur Digital</div>
                <h1 style="margin:14px 0 8px 0;font-size:30px;line-height:1.15;color:#ffffff;">Ton accès LGD est prêt 🚀</h1>
                <p style="margin:0;color:#cfcfcf;font-size:15px;line-height:1.6;">{hello} il ne te reste qu'une étape pour finaliser ton compte.</p>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 30px 6px 30px;">
                <div style="background:rgba(255,190,40,.08);border:1px solid rgba(255,190,40,.22);border-radius:18px;padding:18px;">
                  <p style="margin:0 0 8px 0;color:#f6c400;font-weight:700;font-size:16px;">Accès concerné : {label}</p>
                  <p style="margin:0;color:#e8e8e8;font-size:14px;line-height:1.55;">Clique sur le bouton ci-dessous pour créer ton mot de passe et activer ton espace LGD.</p>
                </div>
              </td>
            </tr>

            <tr>
              <td align="center" style="padding:26px 30px 18px 30px;">
                <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
                   style="display:block;width:100%;max-width:420px;background:linear-gradient(90deg,#ffc400,#ffb000);color:#050505;text-decoration:none;font-weight:800;font-size:16px;padding:16px 20px;border-radius:14px;text-align:center;">
                  Activer mon compte LGD
                </a>
              </td>
            </tr>

            <tr>
              <td style="padding:0 30px 18px 30px;">
                <div style="border-top:1px solid rgba(255,255,255,.08);padding-top:18px;">
                  <p style="margin:0 0 10px 0;color:#ffffff;font-weight:700;">Important sécurité</p>
                  <ul style="margin:0;padding-left:20px;color:#d8d8d8;font-size:14px;line-height:1.7;">
                    <li>Ce lien est valable <strong>{expires_in_hours} heures</strong>.</li>
                    <li>Il est utilisable <strong>une seule fois</strong>.</li>
                    <li>Après activation, il sera automatiquement désactivé.</li>
                  </ul>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:4px 30px 28px 30px;">
                <p style="margin:0;color:#bdbdbd;font-size:13px;line-height:1.6;">
                  Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
                  <span style="color:#f6c400;word-break:break-all;">{safe_url}</span>
                </p>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 30px;background:#030303;border-top:1px solid rgba(255,255,255,.06);text-align:center;">
                <p style="margin:0;color:#8d8d8d;font-size:12px;">© Le Générateur Digital — Tous droits réservés</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_activation_email(
    *,
    to_email: str,
    full_name: str | None,
    access_type: str,
    plan: str,
    activation_url: str,
    expires_in_hours: int,
) -> dict[str, Any]:
    """
    Envoie l'email d'activation via Resend.

    Variables Render à configurer :
    - RESEND_API_KEY : clé API Resend
    - LGD_ACTIVATION_FROM_EMAIL ou RESEND_FROM_EMAIL : ex. "Le Générateur Digital <contact@legenerateurdigital.fr>"
    - LGD_SUPPORT_EMAIL ou RESEND_REPLY_TO : optionnel
    """
    api_key = _env("RESEND_API_KEY")
    clean_to = (to_email or "").strip().lower()

    if not clean_to:
        return {"sent": False, "provider": "resend", "reason": "missing_to_email"}

    if not api_key:
        return {"sent": False, "provider": "resend", "reason": "missing_RESEND_API_KEY"}

    payload: dict[str, Any] = {
        "from": _from_email(),
        "to": [clean_to],
        "subject": _subject(access_type, plan, expires_in_hours),
        "html": _html_body(
            full_name=full_name,
            access_type=access_type,
            plan=plan,
            activation_url=activation_url,
            expires_in_hours=expires_in_hours,
        ),
        "text": _text_body(
            full_name=full_name,
            access_type=access_type,
            plan=plan,
            activation_url=activation_url,
            expires_in_hours=expires_in_hours,
        ),
    }

    reply_to = _reply_to()
    if reply_to:
        payload["reply_to"] = reply_to

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        RESEND_API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return {
                "sent": True,
                "provider": "resend",
                "id": parsed.get("id"),
                "status_code": response.status,
            }
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {
            "sent": False,
            "provider": "resend",
            "status_code": exc.code,
            "error": error_body,
        }
    except Exception as exc:
        return {
            "sent": False,
            "provider": "resend",
            "error": str(exc),
        }
