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
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


# ============================================================
# ENV FACEBOOK / INSTAGRAM / META
# ============================================================

FB_APP_ID = _env("FACEBOOK_APP_ID")
FB_APP_SECRET = _env("FACEBOOK_APP_SECRET")
FB_REDIRECT_URI = _env("FACEBOOK_REDIRECT_URI")

META_APP_ID = _env("META_APP_ID")
META_APP_SECRET = _env("META_APP_SECRET")

IG_CLIENT_ID = _env("INSTAGRAM_CLIENT_ID") or META_APP_ID or FB_APP_ID
IG_CLIENT_SECRET = _env("INSTAGRAM_CLIENT_SECRET") or META_APP_SECRET or FB_APP_SECRET
IG_REDIRECT_URI = _env("INSTAGRAM_REDIRECT_URI")

STATE_SECRET = _env("FACEBOOK_STATE_SECRET", "change_me_long_random")

GRAPH = "https://graph.facebook.com"
GRAPH_V = "v20.0"


# ============================================================
# URL HELPERS
# ============================================================

def _normalized_facebook_redirect_uri() -> str:
    uri = (FB_REDIRECT_URI or "").strip()
    if not uri:
        return ""
    uri = uri.replace("/social/facebook/callback", "/social-connections/facebook/callback")
    uri = uri.replace("//social-connections/facebook/callback", "/social-connections/facebook/callback")
    return uri


def _normalized_instagram_redirect_uri() -> str:
    uri = (IG_REDIRECT_URI or "").strip()
    if uri:
        uri = uri.replace("/social/instagram/callback", "/social-connections/instagram/callback")
        uri = uri.replace("//social-connections/instagram/callback", "/social-connections/instagram/callback")
        return uri

    fb_uri = _normalized_facebook_redirect_uri()
    if fb_uri:
        return fb_uri.replace("/facebook/callback", "/instagram/callback")
    return ""


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


# ============================================================
# ENV CHECKS
# ============================================================

def _require_facebook_env() -> None:
    redirect_uri = _normalized_facebook_redirect_uri()
    missing = []
    if not FB_APP_ID:
        missing.append("FACEBOOK_APP_ID")
    if not FB_APP_SECRET:
        missing.append("FACEBOOK_APP_SECRET")
    if not redirect_uri:
        missing.append("FACEBOOK_REDIRECT_URI")
    if missing:
        raise HTTPException(status_code=500, detail=f"Env Facebook manquants: {', '.join(missing)}")


def _require_instagram_env() -> None:
    redirect_uri = _normalized_instagram_redirect_uri()
    missing = []
    if not IG_CLIENT_ID:
        missing.append("INSTAGRAM_CLIENT_ID ou META_APP_ID")
    if not IG_CLIENT_SECRET:
        missing.append("INSTAGRAM_CLIENT_SECRET ou META_APP_SECRET")
    if not redirect_uri:
        missing.append("INSTAGRAM_REDIRECT_URI")
    if missing:
        raise HTTPException(status_code=500, detail=f"Env Instagram manquants: {', '.join(missing)}")


# ============================================================
# AUTH / USER
# ============================================================

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


# ============================================================
# DB
# ============================================================

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


def _get_existing_facebook_context(db: Session, user_id: int) -> Dict[str, str]:
    _ensure_schema(db)
    row = db.execute(
        text(
            """
            SELECT page_id, page_name
            FROM social_connections
            WHERE user_id=:uid
              AND network='facebook'
              AND is_active=true
              AND LENGTH(COALESCE(access_token,'')) > 0
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).mappings().first()

    if not row:
        return {}

    page_id = str(row.get("page_id") or "").strip()
    page_name = str(row.get("page_name") or "").strip()

    extra: Dict[str, str] = {"facebook": "connected"}
    if page_id:
        extra["page_id"] = page_id
    if page_name:
        extra["page_name"] = page_name
    return extra


# ============================================================
# STATE
# ============================================================

def _sign_state(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(STATE_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return json.dumps({"p": payload, "s": sig}, separators=(",", ":"), sort_keys=True)


def _verify_state(state: str) -> dict:
    try:
        data = json.loads(state)
        payload = data["p"]
        sig = data["s"]
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        exp = hmac.new(STATE_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, exp):
            raise ValueError("bad sig")
        ts = int(payload.get("ts") or 0)
        if ts <= 0 or abs(int(time.time()) - ts) > 900:
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=400, detail="State invalide ou expiré.")


def _safe_user_id_from_state(state: Optional[str]) -> Optional[int]:
    if not state:
        return None
    try:
        payload = _verify_state(state)
        return int(payload["uid"])
    except Exception:
        return None


# ============================================================
# META GRAPH
# ============================================================

def _graph_get(path: str, params: dict) -> dict:
    r = requests.get(f"{GRAPH}/{GRAPH_V}/{path.lstrip('/')}", params=params, timeout=25)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook API error: {j}")
    return r.json()


def _exchange_long_lived_fb(short_token: str) -> dict:
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


def _exchange_long_lived_ig(short_token: str) -> dict:
    r = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": IG_CLIENT_ID,
            "client_secret": IG_CLIENT_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=25,
    )
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Instagram token exchange error: {j}")
    return r.json()


def _pick_instagram_from_pages(pages: list[dict]) -> dict:
    picked = {
        "ig_account_id": "",
        "ig_username": "",
        "source": "",
        "matched_page_id": "",
        "matched_page_name": "",
        "pages_debug": [],
    }

    for page in pages:
        page_id = str(page.get("id") or "").strip()
        page_name = str(page.get("name") or "").strip()

        ig_business = page.get("instagram_business_account") or {}
        ig_connected = page.get("connected_instagram_account") or {}

        ig_business_id = str(ig_business.get("id") or "").strip()
        ig_business_username = str(ig_business.get("username") or "").strip()
        ig_connected_id = str(ig_connected.get("id") or "").strip()
        ig_connected_username = str(ig_connected.get("username") or "").strip()

        picked["pages_debug"].append(
            {
                "page_id": page_id,
                "page_name": page_name,
                "instagram_business_account": {
                    "id": ig_business_id or None,
                    "username": ig_business_username or None,
                },
                "connected_instagram_account": {
                    "id": ig_connected_id or None,
                    "username": ig_connected_username or None,
                },
            }
        )

        if ig_business_id:
            picked.update(
                {
                    "ig_account_id": ig_business_id,
                    "ig_username": ig_business_username,
                    "source": "instagram_business_account",
                    "matched_page_id": page_id,
                    "matched_page_name": page_name,
                }
            )
            return picked

        if ig_connected_id:
            picked.update(
                {
                    "ig_account_id": ig_connected_id,
                    "ig_username": ig_connected_username,
                    "source": "connected_instagram_account",
                    "matched_page_id": page_id,
                    "matched_page_name": page_name,
                }
            )
            return picked

    return picked


# ============================================================
# DEBUG
# ============================================================

@router.get("/debug")
def debug(db: Session = Depends(get_db)):
    try:
        _ensure_schema(db)
        return {
            "ok": True,
            "table": "social_connections",
            "fb_redirect_uri_runtime": _normalized_facebook_redirect_uri(),
            "ig_redirect_uri_runtime": _normalized_instagram_redirect_uri(),
            "callback_path_expected_facebook": "/social-connections/facebook/callback",
            "callback_path_expected_instagram": "/social-connections/instagram/callback",
            "fb_app_id_runtime": FB_APP_ID,
            "ig_app_id_runtime": IG_CLIENT_ID,
            "frontend_planner_url_facebook": _frontend_planner_url({"facebook": "connected"}),
            "frontend_planner_url_instagram": _frontend_planner_url({"instagram": "connected"}),
            "LGD_DEBUG_VERSION": "IG-FB-STABLE-KEEP-FB-2026-03-10",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"social_connections_debug_error: {str(e)}")


# ============================================================
# STATUS
# ============================================================

@router.get("/status")
def status(current_user: Any = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_schema(db)
    uid = _user_id_from_current_user(current_user)
    rows = db.execute(
        text(
            """
            SELECT
                network,
                MAX(CASE WHEN is_active AND LENGTH(COALESCE(access_token,'')) > 0 THEN 1 ELSE 0 END) AS token_ok,
                MAX(CASE WHEN is_active AND COALESCE(page_id,'') <> '' THEN 1 ELSE 0 END) AS page_ok,
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
        token_ok = bool(r.get("token_ok") or 0)
        page_ok = bool(r.get("page_ok") or 0)
        fb_page_ok = bool(r.get("fb_page_ok") or 0)

        if net == "facebook":
            out["networks"][net] = {
                "connected": token_ok,
                "facebook_page_ready": fb_page_ok,
            }
        elif net == "instagram":
            out["networks"][net] = {
                "connected": token_ok and page_ok,
                "facebook_page_ready": None,
            }
        else:
            out["networks"][net] = {
                "connected": token_ok,
                "facebook_page_ready": None,
            }
    return out


# ============================================================
# SAVE / DISCONNECT
# ============================================================

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


# ============================================================
# CONNECT
# ============================================================

@router.post("/{network}/connect")
def connect(network: str, current_user: Any = Depends(get_current_user)):
    net = _normalize_network(network)
    uid = _user_id_from_current_user(current_user)

    if net == "facebook":
        _require_facebook_env()
        redirect_uri = _normalized_facebook_redirect_uri()
        state = _sign_state({"uid": uid, "net": "facebook", "ts": int(time.time())})
        scope = ",".join(
            [
                "email",
                "public_profile",
                "pages_show_list",
                "pages_read_engagement",
                "pages_manage_posts",
            ]
        )

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
                "network": "facebook",
                "redirect_uri_runtime": redirect_uri,
                "app_id_runtime": FB_APP_ID,
                "frontend_planner_url": _frontend_planner_url({"facebook": "connected"}),
            },
        }

    if net == "instagram":
        _require_instagram_env()
        redirect_uri = _normalized_instagram_redirect_uri()
        state = _sign_state({"uid": uid, "net": "instagram", "ts": int(time.time())})

        # IMPORTANT
        # On réduit volontairement le scope au strict minimum accepté
        # pour récupérer le compte pro lié via les pages Facebook.
        # Cela évite l'erreur Meta "Invalid Scopes" observée.
        scope = ",".join(
            [
                "pages_show_list",
                "business_management",
            ]
        )

        auth_url = (
            f"https://www.facebook.com/{GRAPH_V}/dialog/oauth"
            f"?client_id={IG_CLIENT_ID}"
            f"&redirect_uri={requests.utils.quote(redirect_uri, safe='')}"
            f"&state={requests.utils.quote(state, safe='')}"
            f"&scope={requests.utils.quote(scope, safe='')}"
            f"&response_type=code"
        )

        return {
            "ok": True,
            "auth_url": auth_url,
            "debug": {
                "network": "instagram",
                "redirect_uri_runtime": redirect_uri,
                "app_id_runtime": IG_CLIENT_ID,
                "scope_runtime": scope,
                "frontend_planner_url": _frontend_planner_url({"instagram": "connected"}),
            },
        }

    raise HTTPException(status_code=501, detail=f"OAuth non implémenté pour '{net}'.")


# ============================================================
# FACEBOOK CALLBACK
# ============================================================

def _handle_facebook_callback(code: str, state: str, db: Session) -> dict:
    _require_facebook_env()
    redirect_uri = _normalized_facebook_redirect_uri()
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

    long_data = _exchange_long_lived_fb(short_token)
    long_token = str(long_data.get("access_token") or "").strip()
    expires_in = int(long_data.get("expires_in") or 0)
    if not long_token:
        raise HTTPException(status_code=400, detail="Facebook access_token manquant (long-lived).")

    expires_at = datetime.utcnow() + timedelta(seconds=expires_in or 60 * 60 * 24 * 60)
    me = _graph_get("/me", {"access_token": long_token, "fields": "id,name"})
    fb_user_id = str(me.get("id") or "").strip()
    pages = _graph_get(
        "/me/accounts",
        {"access_token": long_token, "fields": "id,name,access_token"},
    ).get("data") or []

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


# ============================================================
# INSTAGRAM CALLBACK
# ============================================================

def _handle_instagram_callback(code: str, state: str, db: Session) -> dict:
    _require_instagram_env()
    redirect_uri = _normalized_instagram_redirect_uri()
    payload = _verify_state(state)
    user_id = int(payload["uid"])

    tok = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "client_id": IG_CLIENT_ID,
            "client_secret": IG_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=25,
    )
    if not tok.ok:
        raise HTTPException(status_code=400, detail=f"Instagram OAuth code exchange failed: {tok.text}")

    short_token = tok.json().get("access_token")
    if not short_token:
        raise HTTPException(status_code=400, detail="Instagram access_token manquant (short).")

    long_data = _exchange_long_lived_ig(short_token)
    long_token = str(long_data.get("access_token") or "").strip()
    expires_in = int(long_data.get("expires_in") or 0)
    if not long_token:
        raise HTTPException(status_code=400, detail="Instagram access_token manquant (long-lived).")

    expires_at = datetime.utcnow() + timedelta(seconds=expires_in or 60 * 60 * 24 * 60)

    pages = _graph_get(
        "/me/accounts",
        {
            "access_token": long_token,
            "fields": "id,name,instagram_business_account{id,username},connected_instagram_account{id,username}",
        },
    ).get("data") or []

    picked = _pick_instagram_from_pages(pages)
    ig_account_id = str(picked.get("ig_account_id") or "").strip()
    ig_username = str(picked.get("ig_username") or "").strip()

    if not ig_account_id:
        _upsert_connection(
            db,
            SaveConnectionIn(
                user_id=user_id,
                network="instagram",
                access_token=long_token,
                refresh_token="",
                expires_at=expires_at,
                is_active=True,
            ),
        )
        return {
            "ok": True,
            "warning": "Connexion Instagram créée, mais aucun compte Instagram professionnel lié n'a été trouvé.",
            "instagram_connected": False,
            "ig_id": None,
            "ig_username": None,
            "selected_source": None,
            "matched_page_id": None,
            "matched_page_name": None,
            "pages_debug": picked.get("pages_debug") or [],
            "user_id": user_id,
        }

    _upsert_connection(
        db,
        SaveConnectionIn(
            user_id=user_id,
            network="instagram",
            access_token=long_token,
            refresh_token="",
            expires_at=expires_at,
            is_active=True,
            page_id=ig_account_id or None,
            page_name=ig_username or None,
        ),
    )

    return {
        "ok": True,
        "user_id": user_id,
        "instagram_connected": True,
        "ig_id": ig_account_id,
        "ig_username": ig_username,
        "selected_source": picked.get("source"),
        "matched_page_id": picked.get("matched_page_id"),
        "matched_page_name": picked.get("matched_page_name"),
        "token_saved": True,
        "pages_debug": picked.get("pages_debug") or [],
    }


# ============================================================
# REDIRECT HTML
# ============================================================

def _redirect_html(target_url: str, title: str, message: str) -> HTMLResponse:
    print("LGD REDIRECT TARGET =", target_url)
    html = f"""
    <!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="0;url={target_url}">
        <title>{title}</title>
        <script>
          window.location.replace({target_url!r});
        </script>
      </head>
      <body style="background:#0b0b0c;color:#f5f5f5;font-family:Arial,sans-serif;padding:40px;">
        <h1 style="color:#facc15;">{title}</h1>
        <p>{message}</p>
        <p><a href="{target_url}" style="color:#facc15;">Cliquer ici si la redirection ne démarre pas</a></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


def _instagram_error_redirect(
    db: Session,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    error_reason: Optional[str] = None,
) -> HTMLResponse:
    extra: Dict[str, Any] = {
        "instagram": "warning",
        "instagram_error": error or error_reason or "oauth_error",
        "instagram_error_code": error_code or "",
        "instagram_error_message": error_message or "",
    }

    state_uid = _safe_user_id_from_state(state)
    if state_uid:
        extra.update(_get_existing_facebook_context(db, state_uid))

    target_url = _frontend_planner_url(extra)
    return _redirect_html(
        target_url,
        "Alerte Instagram",
        error_message or "La connexion Instagram a été interrompue ou refusée.",
    )


# ============================================================
# CALLBACKS
# ============================================================

@router.get("/facebook/callback")
def facebook_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_code: Optional[str] = Query(default=None),
    error_message: Optional[str] = Query(default=None),
    error_reason: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    print("LGD CALLBACK FACEBOOK HIT")

    if error or error_code or error_message or error_reason:
        return _redirect_html(
            _frontend_planner_url(
                {
                    "facebook": "warning",
                    "facebook_error": error or error_reason or "oauth_error",
                    "facebook_error_code": error_code or "",
                    "facebook_error_message": error_message or "",
                }
            ),
            "Alerte Facebook",
            error_message or "La connexion Facebook a été interrompue ou refusée.",
        )

    if not code or not state:
        return _redirect_html(
            _frontend_planner_url({"facebook": "warning"}),
            "Alerte Facebook",
            "Le callback Facebook n'a pas reçu les paramètres OAuth attendus.",
        )

    result = _handle_facebook_callback(code=code, state=state, db=db)
    print("LGD CALLBACK FACEBOOK RESULT =", result)

    if result.get("ok") and result.get("token_saved"):
        target_url = _frontend_planner_url(
            {
                "facebook": "connected",
                "page_id": result.get("page_id") or "",
                "page_name": result.get("page_name") or "",
            }
        )
        return _redirect_html(
            target_url,
            "Connexion Facebook réussie",
            "Redirection vers le Planner LGD…",
        )

    return _redirect_html(
        _frontend_planner_url({"facebook": "warning"}),
        "Alerte Facebook",
        "Connexion Facebook créée, mais la validation de la page a échoué.",
    )


@router.get("/instagram/callback")
def instagram_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_code: Optional[str] = Query(default=None),
    error_message: Optional[str] = Query(default=None),
    error_reason: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    print("LGD CALLBACK INSTAGRAM HIT")

    if error or error_code or error_message or error_reason:
        return _instagram_error_redirect(
            db=db,
            state=state,
            error=error,
            error_code=error_code,
            error_message=error_message,
            error_reason=error_reason,
        )

    if not code or not state:
        return _instagram_error_redirect(
            db=db,
            state=state,
            error="missing_oauth_params",
            error_message="Le callback Instagram n'a pas reçu les paramètres OAuth attendus.",
        )

    result = _handle_instagram_callback(code=code, state=state, db=db)
    print("LGD CALLBACK INSTAGRAM RESULT =", result)

    fb_extra = _get_existing_facebook_context(db, int(result.get("user_id") or 0)) if result.get("user_id") else {}

    if result.get("ok") and result.get("token_saved") and result.get("instagram_connected"):
        target_url = _frontend_planner_url(
            {
                **fb_extra,
                "instagram": "connected",
                "ig_id": result.get("ig_id") or "",
                "ig_name": result.get("ig_username") or "",
            }
        )
        return _redirect_html(
            target_url,
            "Connexion Instagram réussie",
            "Redirection vers le Planner LGD…",
        )

    return _redirect_html(
        _frontend_planner_url(
            {
                **fb_extra,
                "instagram": "warning",
            }
        ),
        "Alerte Instagram",
        "Connexion Instagram créée, mais aucun compte professionnel lié n'a été trouvé.",
    )


@router.get("/{network}/callback")
def callback(
    network: str,
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_code: Optional[str] = Query(default=None),
    error_message: Optional[str] = Query(default=None),
    error_reason: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    print("LGD GENERIC CALLBACK HIT", network)
    net = _normalize_network(network)

    if net == "facebook":
        if error or error_code or error_message or error_reason:
            return _redirect_html(
                _frontend_planner_url(
                    {
                        "facebook": "warning",
                        "facebook_error": error or error_reason or "oauth_error",
                        "facebook_error_code": error_code or "",
                        "facebook_error_message": error_message or "",
                    }
                ),
                "Alerte Facebook",
                error_message or "La connexion Facebook a été interrompue ou refusée.",
            )

        if not code or not state:
            return _redirect_html(
                _frontend_planner_url({"facebook": "warning"}),
                "Alerte Facebook",
                "Le callback Facebook n'a pas reçu les paramètres OAuth attendus.",
            )

        result = _handle_facebook_callback(code=code, state=state, db=db)
        print("LGD GENERIC CALLBACK FACEBOOK RESULT =", result)

        if result.get("ok") and result.get("token_saved"):
            target_url = _frontend_planner_url(
                {
                    "facebook": "connected",
                    "page_id": result.get("page_id") or "",
                    "page_name": result.get("page_name") or "",
                }
            )
            return _redirect_html(
                target_url,
                "Connexion Facebook réussie",
                "Redirection vers le Planner LGD…",
            )

        return _redirect_html(
            _frontend_planner_url({"facebook": "warning"}),
            "Alerte Facebook",
            "Connexion Facebook créée, mais la validation de la page a échoué.",
        )

    if net == "instagram":
        if error or error_code or error_message or error_reason:
            return _instagram_error_redirect(
                db=db,
                state=state,
                error=error,
                error_code=error_code,
                error_message=error_message,
                error_reason=error_reason,
            )

        if not code or not state:
            return _instagram_error_redirect(
                db=db,
                state=state,
                error="missing_oauth_params",
                error_message="Le callback Instagram n'a pas reçu les paramètres OAuth attendus.",
            )

        result = _handle_instagram_callback(code=code, state=state, db=db)
        print("LGD GENERIC CALLBACK INSTAGRAM RESULT =", result)

        fb_extra = _get_existing_facebook_context(db, int(result.get("user_id") or 0)) if result.get("user_id") else {}

        if result.get("ok") and result.get("token_saved") and result.get("instagram_connected"):
            target_url = _frontend_planner_url(
                {
                    **fb_extra,
                    "instagram": "connected",
                    "ig_id": result.get("ig_id") or "",
                    "ig_name": result.get("ig_username") or "",
                }
            )
            return _redirect_html(
                target_url,
                "Connexion Instagram réussie",
                "Redirection vers le Planner LGD…",
            )

        return _redirect_html(
            _frontend_planner_url(
                {
                    **fb_extra,
                    "instagram": "warning",
                }
            ),
            "Alerte Instagram",
            "Connexion Instagram créée, mais aucun compte professionnel lié n'a été trouvé.",
        )

    raise HTTPException(status_code=501, detail=f"Callback OAuth non implémenté pour '{net}'.")
