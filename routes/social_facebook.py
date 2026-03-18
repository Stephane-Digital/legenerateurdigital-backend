from __future__ import annotations

import os
import time
import hmac
import json
import hashlib
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session


# === SAFE IMPORTS (adapte sans casser) ===
def _get_db_dep():
    # essaie les chemins les plus probables dans LGD
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
    raise RuntimeError("get_db introuvable. Ajuste l'import dans routes/social_facebook.py (fonction _get_db_dep).")

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
    raise RuntimeError("get_current_user introuvable. Ajuste l'import dans routes/social_facebook.py (fonction _get_user_dep).")

get_db = _get_db_dep()
get_current_user = _get_user_dep()


router = APIRouter(prefix="/social/facebook", tags=["Social • Facebook"])


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


FB_APP_ID = _env("FACEBOOK_APP_ID")
FB_APP_SECRET = _env("FACEBOOK_APP_SECRET")
FB_REDIRECT_URI = _env("FACEBOOK_REDIRECT_URI")
FB_STATE_SECRET = _env("FACEBOOK_STATE_SECRET", "change_me")


GRAPH = "https://graph.facebook.com"
GRAPH_V = "v20.0"  # OK (tu peux monter/descendre si besoin)


def _require_env():
    if not FB_APP_ID or not FB_APP_SECRET or not FB_REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="Facebook env manquants. Vérifie FACEBOOK_APP_ID / FACEBOOK_APP_SECRET / FACEBOOK_REDIRECT_URI.",
        )


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
        # anti replay simple
        ts = int(payload.get("ts") or 0)
        if ts <= 0 or abs(int(time.time()) - ts) > 600:
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=400, detail="State invalide ou expiré.")


def _ensure_tables(db: Session) -> None:
    """
    Table additive (sans toucher tes models) :
    - lgd_social_connections : tokens + page sélectionnée
    """
    db.execute(text("""
    CREATE TABLE IF NOT EXISTS lgd_social_connections (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      provider VARCHAR(32) NOT NULL,
      fb_user_id VARCHAR(64),
      page_id VARCHAR(64),
      page_name VARCHAR(255),
      page_access_token TEXT,
      user_access_token TEXT,
      token_expires_at TIMESTAMP NULL,
      created_at TIMESTAMP NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
      UNIQUE(user_id, provider)
    );
    """))
    db.commit()


def _upsert_connection(
    db: Session,
    user_id: int,
    provider: str,
    fb_user_id: Optional[str] = None,
    user_access_token: Optional[str] = None,
    page_id: Optional[str] = None,
    page_name: Optional[str] = None,
    page_access_token: Optional[str] = None,
    expires_at_iso: Optional[str] = None,
) -> None:
    _ensure_tables(db)

    db.execute(
        text("""
        INSERT INTO lgd_social_connections
          (user_id, provider, fb_user_id, user_access_token, page_id, page_name, page_access_token, token_expires_at, updated_at)
        VALUES
          (:user_id, :provider, :fb_user_id, :user_access_token, :page_id, :page_name, :page_access_token,
           CASE WHEN :expires_at_iso IS NULL OR :expires_at_iso = '' THEN NULL ELSE (:expires_at_iso)::timestamp END,
           NOW())
        ON CONFLICT (user_id, provider)
        DO UPDATE SET
          fb_user_id = COALESCE(EXCLUDED.fb_user_id, lgd_social_connections.fb_user_id),
          user_access_token = COALESCE(EXCLUDED.user_access_token, lgd_social_connections.user_access_token),
          page_id = COALESCE(EXCLUDED.page_id, lgd_social_connections.page_id),
          page_name = COALESCE(EXCLUDED.page_name, lgd_social_connections.page_name),
          page_access_token = COALESCE(EXCLUDED.page_access_token, lgd_social_connections.page_access_token),
          token_expires_at = COALESCE(EXCLUDED.token_expires_at, lgd_social_connections.token_expires_at),
          updated_at = NOW();
        """),
        {
            "user_id": int(user_id),
            "provider": provider,
            "fb_user_id": fb_user_id,
            "user_access_token": user_access_token,
            "page_id": page_id,
            "page_name": page_name,
            "page_access_token": page_access_token,
            "expires_at_iso": expires_at_iso or "",
        },
    )
    db.commit()


def _get_connection(db: Session, user_id: int, provider: str) -> Optional[dict]:
    _ensure_tables(db)
    row = db.execute(
        text("""
        SELECT user_id, provider, fb_user_id, page_id, page_name, page_access_token, user_access_token, token_expires_at
        FROM lgd_social_connections
        WHERE user_id=:user_id AND provider=:provider
        LIMIT 1;
        """),
        {"user_id": int(user_id), "provider": provider},
    ).mappings().first()
    return dict(row) if row else None


def _graph_get(path: str, params: dict) -> dict:
    r = requests.get(f"{GRAPH}/{GRAPH_V}/{path.lstrip('/')}", params=params, timeout=25)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook API error: {j}")
    return r.json()


def _graph_post(path: str, params: dict) -> dict:
    r = requests.post(f"{GRAPH}/{GRAPH_V}/{path.lstrip('/')}", data=params, timeout=25)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook API error: {j}")
    return r.json()


def _exchange_long_lived(short_token: str) -> dict:
    # GET /oauth/access_token?grant_type=fb_exchange_token&client_id=&client_secret=&fb_exchange_token=
    res = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=25,
    )
    if not res.ok:
        try:
            j = res.json()
        except Exception:
            j = {"error": {"message": res.text}}
        raise HTTPException(status_code=400, detail=f"Token exchange error: {j}")
    return res.json()


@router.get("/start")
def facebook_oauth_start(current_user: Any = Depends(get_current_user)):
    """
    Retourne l'URL OAuth Meta.
    """
    _require_env()

    # scopes minimal + Pages (publishing)
    scope = ",".join([
        "email",
        "public_profile",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
    ])

    state = _sign_state({"uid": int(getattr(current_user, "id")), "ts": int(time.time())})

    url = (
        "https://www.facebook.com/v20.0/dialog/oauth"
        f"?client_id={FB_APP_ID}"
        f"&redirect_uri={FB_REDIRECT_URI}"
        f"&state={requests.utils.quote(state)}"
        f"&scope={requests.utils.quote(scope)}"
        f"&response_type=code"
    )

    return {"auth_url": url}


@router.get("/callback")
def facebook_oauth_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """
    Callback Meta.
    1) échange code -> short token
    2) échange short -> long-lived token
    3) récupère fb_user_id
    4) récupère pages + page tokens
    5) stocke user_access_token (long-lived) + fb_user_id
    Renvoie une page HTML de redirection OU JSON selon ton front.
    """
    _require_env()

    payload = _verify_state(state)
    user_id = int(payload["uid"])

    # 1) code -> short token
    tok = requests.get(
        f"{GRAPH}/{GRAPH_V}/oauth/access_token",
        params={
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri": FB_REDIRECT_URI,
            "code": code,
        },
        timeout=25,
    )
    if not tok.ok:
        raise HTTPException(status_code=400, detail=f"OAuth code exchange failed: {tok.text}")

    short = tok.json().get("access_token")
    if not short:
        raise HTTPException(status_code=400, detail="Facebook access_token manquant (short).")

    # 2) short -> long-lived
    long_data = _exchange_long_lived(short)
    long_token = long_data.get("access_token")
    expires_in = int(long_data.get("expires_in") or 0)

    if not long_token:
        raise HTTPException(status_code=400, detail="Facebook access_token manquant (long-lived).")

    # expires_at (approx)
    expires_at_iso = ""
    if expires_in > 0:
        # on stocke un timestamp "now + expires"
        expires_at_iso = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(int(time.time()) + expires_in),
        )

    # 3) fb user
    me = _graph_get("/me", {"access_token": long_token, "fields": "id,name"})
    fb_user_id = str(me.get("id") or "")

    # 4) pages
    pages = _graph_get("/me/accounts", {"access_token": long_token, "fields": "id,name,access_token"}).get("data") or []
    safe_pages = []
    for p in pages:
        safe_pages.append({
            "id": str(p.get("id") or ""),
            "name": str(p.get("name") or ""),
            # IMPORTANT : on ne renvoie pas le token en clair si tu veux sécuriser côté front.
            # Ici on le renvoie pour simplifier ta phase dev — en prod, tu peux retirer.
            "access_token": str(p.get("access_token") or ""),
        })

    # 5) store connection (user token)
    _upsert_connection(
        db=db,
        user_id=user_id,
        provider="facebook",
        fb_user_id=fb_user_id,
        user_access_token=long_token,
        expires_at_iso=expires_at_iso or None,
    )

    # renvoie JSON (simple)
    return {"ok": True, "pages": safe_pages, "fb_user_id": fb_user_id, "token_expires_at": expires_at_iso or None}


@router.post("/select-page")
def facebook_select_page(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """
    Stocke la Page choisie + son Page Access Token.
    body: { page_id, page_name, page_access_token }
    """
    page_id = str(body.get("page_id") or "").strip()
    page_name = str(body.get("page_name") or "").strip()
    page_token = str(body.get("page_access_token") or "").strip()

    if not page_id or not page_token:
        raise HTTPException(status_code=400, detail="page_id et page_access_token requis.")

    _upsert_connection(
        db=db,
        user_id=int(getattr(current_user, "id")),
        provider="facebook",
        page_id=page_id,
        page_name=page_name or None,
        page_access_token=page_token,
    )

    return {"ok": True, "page_id": page_id, "page_name": page_name or None}


@router.get("/status")
def facebook_status(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    c = _get_connection(db, int(getattr(current_user, "id")), "facebook")
    if not c:
        return {"connected": False}

    connected = bool(c.get("page_access_token")) and bool(c.get("page_id"))
    return {
        "connected": connected,
        "page_id": c.get("page_id"),
        "page_name": c.get("page_name"),
        "token_expires_at": str(c.get("token_expires_at")) if c.get("token_expires_at") else None,
    }

@router.get("/start-test")
def start_test():
    _require_env()

    scope = ",".join([
        "email",
        "public_profile",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
    ])

    url = (
        "https://www.facebook.com/v20.0/dialog/oauth"
        f"?client_id={FB_APP_ID}"
        f"&redirect_uri={FB_REDIRECT_URI}"
        f"&scope={scope}"
        f"&response_type=code"
    )

    return {"auth_url": url}
