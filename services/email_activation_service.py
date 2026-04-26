from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from html import escape
from typing import Any


RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_SUPPORT_EMAIL = "contact@legenerateurdigital.fr"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _subject(access_type: str, plan: str) -> str:
    access = (access_type or "").strip().lower()
    clean_plan = (plan or "").strip().lower()

    if access == "trial" or clean_plan == "trial":
        return "🚀 Active ton essai gratuit LGD — lien valable 48h"

    label = {
        "essentiel": "Essentiel",
        "pro": "Pro",
        "ultime": "Ultime",
    }.get(clean_plan, "LGD")

    return f"🚀 Active ton accès LGD {label} — lien valable 48h"


def _first_name(full_name: str | None, email: str) -> str:
    raw = (full_name or "").strip()
    if raw:
        return raw.split(" ")[0]
    return (email or "Bonjour").split("@")[0]


def _plain_text(*, first_name: str, activation_url: str, expires_in_hours: int) -> str:
    return f"""Bonjour {first_name},

Ton accès à Le Générateur Digital est prêt.

Clique ici pour finaliser ton compte :
{activation_url}

Important :
- Ce lien est valable {expires_in_hours} heures.
- Il est utilisable une seule fois.
- Après utilisation, il sera automatiquement désactivé pour ta sécurité.

Une fois ton compte activé, tu pourras accéder à ton dashboard LGD, Coach Alex, l'Éditeur Intelligent, Emailing IA et Lead Engine IA.

Si le lien a expiré, retourne sur la page d'activation pour demander un nouveau lien.

À très vite,
L'équipe Le Générateur Digital
"""


def _html_body(*, first_name: str, activation_url: str, expires_in_hours: int) -> str:
    safe_name = escape(first_name)
    safe_url = escape(activation_url, quote=True)

    return f"""
<!doctype html>
<html lang="fr">
  <body style="margin:0;padding:0;background:#050505;font-family:Arial,Helvetica,sans-serif;color:#ffffff;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#050505;padding:32px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#111111;border:1px solid rgba(255,190,0,.25);border-radius:22px;overflow:hidden;">
            <tr>
              <td style="padding:34px 30px 18px;text-align:center;">
                <div style="display:inline-block;padding:8px 14px;border:1px solid rgba(255,190,0,.35);border-radius:999px;color:#ffcc33;font-weight:700;font-size:13px;letter-spacing:.08em;">
                  LE GÉNÉRATEUR DIGITAL
                </div>
                <h1 style="margin:22px 0 10px;font-size:32px;line-height:1.12;color:#ffcc00;">
                  Ton accès LGD est prêt 🚀
                </h1>
                <p style="margin:0;color:#d7d7d7;font-size:16px;line-height:1.55;">
                  Bonjour {safe_name}, il ne te reste qu’une étape pour finaliser ton compte.
                </p>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 30px 8px;text-align:center;">
                <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
                   style="display:block;background:linear-gradient(90deg,#f5b400,#ffd45a);color:#050505;text-decoration:none;font-weight:800;font-size:17px;padding:17px 22px;border-radius:16px;">
                  Activer mon compte LGD
                </a>
              </td>
            </tr>

            <tr>
              <td style="padding:22px 30px 4px;">
                <div style="background:#0a0a0a;border:1px solid rgba(255,190,0,.18);border-radius:18px;padding:18px;">
                  <p style="margin:0 0 10px;color:#ffffff;font-weight:700;">🔐 Important</p>
                  <ul style="margin:0;padding-left:20px;color:#d7d7d7;font-size:14px;line-height:1.7;">
                    <li>Ce lien est valable <strong style="color:#ffcc00;">{expires_in_hours} heures</strong>.</li>
                    <li>Il est utilisable <strong style="color:#ffcc00;">une seule fois</strong>.</li>
                    <li>Après activation, il sera automatiquement désactivé.</li>
                  </ul>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:22px 30px 10px;">
                <p style="margin:0;color:#d7d7d7;font-size:15px;line-height:1.65;">
                  Dès l’activation, tu accèdes à ton dashboard LGD, Coach Alex, l’Éditeur Intelligent,
                  Emailing IA et Lead Engine IA.
                </p>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 30px 32px;">
                <p style="margin:0;color:#8f8f8f;font-size:12px;line-height:1.55;">
                  Si le bouton ne fonctionne pas, copie-colle ce lien dans ton navigateur :<br>
                  <span style="color:#ffcc00;word-break:break-all;">{safe_url}</span>
                </p>
              </td>
            </tr>
          </table>

          <p style="margin:18px 0 0;color:#777;font-size:12px;">
            © Le Générateur Digital — Tous droits réservés
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def send_activation_email_safely(
    *,
    to_email: str,
    activation_url: str,
    access_type: str = "trial",
    plan: str = "trial",
    expires_in_hours: int = 48,
    full_name: str | None = None,
) -> dict[str, Any]:
    """
    Envoie l'email d'activation LGD via Resend.
    Fonction volontairement safe : elle ne lève jamais d'exception pour ne pas casser le webhook SIO.
    """
    clean_email = (to_email or "").strip().lower()
    clean_url = (activation_url or "").strip()

    if not clean_email or not clean_url:
        return {"sent": False, "reason": "missing_email_or_activation_url"}

    api_key = _env("RESEND_API_KEY")
    from_email = _env("LGD_ACTIVATION_FROM_EMAIL", f"Le Générateur Digital <{DEFAULT_SUPPORT_EMAIL}>")
    support_email = _env("LGD_SUPPORT_EMAIL", DEFAULT_SUPPORT_EMAIL)

    if not api_key:
        return {"sent": False, "reason": "missing_resend_api_key"}

    first_name = _first_name(full_name, clean_email)

    payload = {
        "from": from_email,
        "to": [clean_email],
        "reply_to": [support_email],
        "subject": _subject(access_type, plan),
        "html": _html_body(
            first_name=first_name,
            activation_url=clean_url,
            expires_in_hours=int(expires_in_hours or 48),
        ),
        "text": _plain_text(
            first_name=first_name,
            activation_url=clean_url,
            expires_in_hours=int(expires_in_hours or 48),
        ),
    }

    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "LGD-Backend/1.0",
},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {"raw": body}

            return {
                "sent": 200 <= int(response.status) < 300,
                "status_code": int(response.status),
                "resend_response": data,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "sent": False,
            "status_code": int(exc.code),
            "reason": "resend_http_error",
            "response": body,
        }
    except Exception as exc:
        return {
            "sent": False,
            "reason": "send_exception",
            "error": repr(exc),
        }
