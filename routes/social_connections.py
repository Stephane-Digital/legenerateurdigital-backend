from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import settings


def _get_db_dep():
    try:
        from database import get_db  # type: ignore
        return get_db
    except Exception:
        pass
    try:
        from db import get_db  # type: ignore
        return get_db
    except Exception:
        pass
    try:
        from core.database import get_db  # type: ignore
        return get_db
    except Exception:
        pass
    raise RuntimeError("get_db introuvable. Ajuste l'import dans routes/social_connections.py (_get_db_dep).")


def _get_user_dep():
    try:
        from auth import get_current_user  # type: ignore
        return get_current_user
    except Exception:
        pass
    try:
        from routes.auth import get_current_user  # type: ignore
        return get_current_user
    except Exception:
        pass
    try:
        from deps import get_current_user  # type: ignore
        return get_current_user
    except Exception:
        pass
    raise RuntimeError("get_current_user introuvable. Ajuste l'import dans routes/social_connections.py (_get_user_dep).")


get_db = _get_db_dep()
get_current_user = _get_user_dep()

router = APIRouter(prefix="/social-connections", tags=["Social Connections"])


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


FB_APP_ID = _env("FACEBOOK_APP_ID")
FB_APP_SECRET = _env("FACEBOOK_APP_SECRET")
FB_REDIRECT_URI = _env("FACEBOOK_REDIRECT_URI")
FB_STATE_SECRET = _env("FACEBOOK_STATE_SECRET", "change_me_long_random")

GRAPH = "https://graph.facebook.com"
GRAPH_V = "v20.0"


def _normalized_redirect_uri() -> str:
    uri = (FB_REDIRECT_URI or "").strip()
    if not uri:
        return ""
    uri = uri.replace("/social/facebook/callback", "/social-connections/facebook/callback")
    uri = uri.replace("//social-connections/facebook/callback", "/social-connections/facebook/callback")
    return uri


def _frontend_planner_url(extra: Optional[Dict[str, Any]] = None) -> str:
    base = (
        (getattr(settings, "FRONTEND_URL", "") or "").strip()
        or _env("FRONTEND_URL")
        or "http://localhost:3000"
    ).rstrip("/")
    path = "/dashboard/automatisations/reseaux_sociaux/planner"
    query = dict(extra or {})
    query["ts"] = str(int(time.time()))
    return f"{base}{path}?{urlencode(query)}"


def _require_facebook_env() -> None:
    redirect_uri = _normalized_redirect_uri()
    missing = []
    if not FB_APP_ID:
        missing.append("FACEBOOK_APP_ID")
    if not FB_APP_SECRET:
        missing.append("FACEBOOK_APP_SECRET")
    if not redirect_uri:
        missing.append("FACEBOOK_REDIRECT_URI")
    if missing:
        raise HTTPException(status_code=500, detail=f"Env Facebook manquants: {', '.join(missing)}")


def _user_id_from_current_user(current_user: Any) -> int:
    if current_user is None:
        raise HTTPException(status_code=401, detail="Non authentifié")
    if isinstance(current_user, dict):
        uid = current_user.get("id")
    else:
        uid = getattr(current_user, "id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="Utilisateur authentifié invalide (id manquant)")
    try:
        return int(uid)
    except Exception:
        raise HTTPException(status_code=401, detail="Utilisateur authentifié invalide (id non exploitable)")


def _ensure_schema(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS social_connections (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                network VARCHAR(50) NOT NULL,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TIMESTAMP WITHOUT TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
            """
        )
    )

    db.execute(text("ALTER TABLE social_connections ADD COLUMN IF NOT EXISTS page_id VARCHAR(64);"))
    db.execute(text("ALTER TABLE social_connections ADD COLUMN IF NOT EXISTS page_name VARCHAR(255);"))
    db.execute(text("ALTER TABLE social_connections ADD COLUMN IF NOT EXISTS page_access_token TEXT;"))
    db.execute(text("ALTER TABLE social_connections ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
    db.execute(text("ALTER TABLE social_connections ADD COLUMN IF NOT EXISTS fb_user_id VARCHAR(64);"))

    db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_social_connections_user_network
            ON social_connections (user_id, network);
            """
        )
    )

    db.commit()


class SaveConnectionIn(BaseModel):
    user_id: int = Field(..., ge=1)
    network: str = Field(..., description="facebook / instagram / pinterest")
    access_token: str = Field(..., min_length=1)
    refresh_token: str = Field("", description="optional")
    expires_at: Optional[datetime] = None
    is_active: bool = True
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    page_access_token: Optional[str] = None
    fb_user_id: Optional[str] = None


def _normalize_network(net: str) -> str:
    v = (net or "").strip().lower()
    if v in ("fb", "facebook"):
        return "facebook"
    if v in ("ig", "instagram"):
        return "instagram"
    if v in ("pin", "pinterest"):
        return "pinterest"
    return v


def _upsert_connection(db: Session, payload: SaveConnectionIn) -> None:
    _ensure_schema(db)
    net = _normalize_network(payload.network)
    exp = payload.expires_at or (datetime.utcnow() + timedelta(days=60))

    db.execute(
        text(
            """
            INSERT INTO social_connections (
                user_id, network, access_token, refresh_token, expires_at, is_active,
                created_at, updated_at, page_id, page_name, page_access_token, fb_user_id
            )
            VALUES (
                :user_id, :network, :access_token, :refresh_token, :expires_at, :is_active,
                NOW(), NOW(), :page_id, :page_name, :page_access_token, :fb_user_id
            )
            ON CONFLICT (user_id, network)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                is_active = EXCLUDED.is_active,
                updated_at = NOW(),
                page_id = COALESCE(EXCLUDED.page_id, social_connections.page_id),
                page_name = COALESCE(EXCLUDED.page_name, social_connections.page_name),
                page_access_token = COALESCE(EXCLUDED.page_access_token, social_connections.page_access_token),
                fb_user_id = COALESCE(EXCLUDED.fb_user_id, social_connections.fb_user_id);
            """
        ),
        {
            "user_id": payload.user_id,
            "network": net,
            "access_token": payload.access_token,
            "refresh_token": payload.refresh_token or "",
            "expires_at": exp,
            "is_active": bool(payload.is_active),
            "page_id": payload.page_id,
            "page_name": payload.page_name,
            "page_access_token": payload.page_access_token,
            "fb_user_id": payload.fb_user_id,
        },
    )
    db.commit()


def _sign_state(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(FB_STATE_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return json.dumps({"p": payload, "s": sig}, separators=(",", ":"), sort_keys=True)


def _verify_state(state: str) -> dict:
    try:
        data = json.loads(state)
        payload = data["p"]
        sig = data["s"]
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        exp = hmac.new(FB_STATE_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, exp):
            raise ValueError("bad sig")
        ts = int(payload.get("ts") or 0)
        if ts <= 0 or abs(int(time.time()) - ts) > 900:
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=400, detail="State invalide ou expiré.")


def _graph_get(path: str, params: dict) -> dict:
    r = requests.get(f"{GRAPH}/{GRAPH_V}/{path.lstrip('/')}", params=params, timeout=25)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook API error: {j}")
    return r.json()


def _exchange_long_lived(short_token: str) -> dict:
    r = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=25,
    )
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Token exchange error: {j}")
    return r.json()


@router.get("/debug")
def debug(db: Session = Depends(get_db)):
    try:
        _ensure_schema(db)
        return {
            "ok": True,
            "table": "social_connections",
            "redirect_uri_runtime": _normalized_redirect_uri(),
            "callback_path_expected": "/social-connections/facebook/callback",
            "app_id_runtime": FB_APP_ID,
            "frontend_planner_url": _frontend_planner_url({"facebook": "connected"}),
            "LGD_DEBUG_VERSION": "FORCE-REDIRECT-2026-03-09",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"social_connections_debug_error: {str(e)}")


@router.get("/status")
def status(current_user: Any = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_schema(db)
    uid = _user_id_from_current_user(current_user)
    rows = db.execute(
        text(
            """
            SELECT
                network,
                MAX(CASE WHEN is_active AND LENGTH(COALESCE(access_token,'')) > 0 THEN 1 ELSE 0 END) AS ok,
                MAX(
                    CASE
                        WHEN network='facebook'
                         AND is_active
                         AND LENGTH(COALESCE(page_access_token,'')) > 0
                         AND COALESCE(page_id,'') <> ''
                        THEN 1 ELSE 0
                    END
                ) AS fb_page_ok
            FROM social_connections
            WHERE user_id=:uid
            GROUP BY network
            """
        ),
        {"uid": uid},
    ).mappings().all()

    out: Dict[str, Any] = {"ok": True, "networks": {}}
    for r in rows:
        net = str(r.get("network") or "")
        out["networks"][net] = {
            "connected": bool(r.get("ok") or 0),
            "facebook_page_ready": bool(r.get("fb_page_ok") or 0) if net == "facebook" else None,
        }
    return out


@router.post("/save")
def save_connection(payload: SaveConnectionIn, db: Session = Depends(get_db)):
    _upsert_connection(db, payload)
    return {"ok": True}


@router.post("/disconnect/{network}")
def disconnect(network: str, current_user: Any = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_schema(db)
    net = _normalize_network(network)
    uid = _user_id_from_current_user(current_user)
    db.execute(
        text(
            """
            UPDATE social_connections
            SET is_active=false,
                updated_at=NOW(),
                page_id=NULL,
                page_name=NULL,
                page_access_token=NULL
            WHERE user_id=:uid AND network=:net
            """
        ),
        {"uid": uid, "net": net},
    )
    db.commit()
    return {"ok": True}


@router.post("/{network}/connect")
def connect(network: str, current_user: Any = Depends(get_current_user)):
    net = _normalize_network(network)
    if net != "facebook":
        raise HTTPException(status_code=501, detail=f"OAuth non implémenté pour '{net}'.")

    _require_facebook_env()
    uid = _user_id_from_current_user(current_user)
    redirect_uri = _normalized_redirect_uri()

    state = _sign_state({"uid": uid, "net": "facebook", "ts": int(time.time())})
    scope = ",".join(["email", "public_profile", "pages_show_list", "pages_read_engagement", "pages_manage_posts"])

    auth_url = (
        f"https://www.facebook.com/{GRAPH_V}/dialog/oauth"
        f"?client_id={FB_APP_ID}"
        f"&redirect_uri={requests.utils.quote(redirect_uri, safe='')}"
        f"&state={requests.utils.quote(state, safe='')}"
        f"&scope={requests.utils.quote(scope, safe='')}"
        f"&response_type=code"
    )

    return {
        "ok": True,
        "auth_url": auth_url,
        "debug": {
            "redirect_uri_runtime": redirect_uri,
            "app_id_runtime": FB_APP_ID,
            "frontend_planner_url": _frontend_planner_url({"facebook": "connected"}),
        },
    }


def _handle_facebook_callback(code: str, state: str, db: Session) -> dict:
    _require_facebook_env()
    redirect_uri = _normalized_redirect_uri()
    payload = _verify_state(state)
    user_id = int(payload["uid"])

    tok = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=25,
    )
    if not tok.ok:
        raise HTTPException(status_code=400, detail=f"OAuth code exchange failed: {tok.text}")

    short_token = tok.json().get("access_token")
    if not short_token:
        raise HTTPException(status_code=400, detail="Facebook access_token manquant (short).")

    long_data = _exchange_long_lived(short_token)
    long_token = str(long_data.get("access_token") or "").strip()
    expires_in = int(long_data.get("expires_in") or 0)
    if not long_token:
        raise HTTPException(status_code=400, detail="Facebook access_token manquant (long-lived).")

    expires_at = datetime.utcnow() + timedelta(seconds=expires_in or 60 * 60 * 24 * 60)
    me = _graph_get("/me", {"access_token": long_token, "fields": "id,name"})
    fb_user_id = str(me.get("id") or "").strip()
    pages = _graph_get("/me/accounts", {"access_token": long_token, "fields": "id,name,access_token"}).get("data") or []

    if not pages:
        _upsert_connection(
            db,
            SaveConnectionIn(
                user_id=user_id,
                network="facebook",
                access_token=long_token,
                refresh_token="",
                expires_at=expires_at,
                is_active=True,
                fb_user_id=fb_user_id or None,
            ),
        )
        return {
            "ok": True,
            "warning": "Connexion Facebook créée, mais aucune page n'a été trouvée via /me/accounts.",
            "pages": [],
        }

    first = pages[0] or {}
    page_id = str(first.get("id") or "").strip()
    page_name = str(first.get("name") or "").strip()
    page_access_token = str(first.get("access_token") or "").strip()

    _upsert_connection(
        db,
        SaveConnectionIn(
            user_id=user_id,
            network="facebook",
            access_token=long_token,
            refresh_token="",
            expires_at=expires_at,
            is_active=True,
            page_id=page_id or None,
            page_name=page_name or None,
            page_access_token=page_access_token or None,
            fb_user_id=fb_user_id or None,
        ),
    )

    return {
        "ok": True,
        "user_id": user_id,
        "fb_user_id": fb_user_id,
        "page_id": page_id,
        "page_name": page_name,
        "token_saved": True,
        "pages": [
            {
                "id": str(p.get("id") or ""),
                "name": str(p.get("name") or ""),
                "has_access_token": bool(str(p.get("access_token") or "").strip()),
            }
            for p in pages
        ],
    }


def _redirect_html(target_url: str) -> HTMLResponse:
    print("LGD REDIRECT TARGET =", target_url)
    html = f"""
    <!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="0;url={target_url}">
        <title>Redirection LGD…</title>
        <script>
          window.location.replace({target_url!r});
        </script>
      </head>
      <body style="background:#0b0b0c;color:#f5f5f5;font-family:Arial,sans-serif;padding:40px;">
        <h1 style="color:#facc15;">Connexion Facebook réussie</h1>
        <p>Redirection vers le Planner LGD…</p>
        <p><a href="{target_url}" style="color:#facc15;">Cliquer ici si la redirection ne démarre pas</a></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@router.get("/facebook/callback")
def facebook_callback(code: str, state: str, db: Session = Depends(get_db)):
    print("LGD CALLBACK FACEBOOK HIT")
    result = _handle_facebook_callback(code=code, state=state, db=db)
    print("LGD CALLBACK RESULT =", result)

    if result.get("ok") and result.get("token_saved"):
        target_url = _frontend_planner_url(
            {
                "facebook": "connected",
                "page_id": result.get("page_id") or "",
                "page_name": result.get("page_name") or "",
            }
        )
        return _redirect_html(target_url)

    return _redirect_html(_frontend_planner_url({"facebook": "warning"}))


@router.get("/{network}/callback")
def callback(network: str, request: Request, code: str, state: str, db: Session = Depends(get_db)):
    print("LGD GENERIC CALLBACK HIT", network)
    net = _normalize_network(network)
    if net != "facebook":
        raise HTTPException(status_code=501, detail=f"Callback OAuth non implémenté pour '{net}'.")

    result = _handle_facebook_callback(code=code, state=state, db=db)
    print("LGD GENERIC CALLBACK RESULT =", result)

    if result.get("ok") and result.get("token_saved"):
        target_url = _frontend_planner_url(
            {
                "facebook": "connected",
                "page_id": result.get("page_id") or "",
                "page_name": result.get("page_name") or "",
            }
        )
        return _redirect_html(target_url)

    return _redirect_html(_frontend_planner_url({"facebook": "warning"}))
