from __future__ import annotations

"""
LGD — Jobs Publisher (Facebook)
--------------------------------
Publie automatiquement les posts Facebook "dus" (scheduled_at <= NOW()).

Objectif (PROPRE + ROBUSTE) :
✅ Compatible schéma FR : reseau / date_programmee / contenu / status (+ statut optionnel)
✅ Compatible schéma EN : network / scheduled_at / content_text / status
✅ Compat tokens :
   - Priorité : lgd_social_connections (page_id + page_access_token)
   - Fallback : social_connections (network='facebook' + access_token) = user token
     => récupère /me/accounts, prend la 1ère page, stocke page_id + page_access_token dans lgd_social_connections
✅ Fallback LINK si pas de link DB : https://legenerateurdigital.systeme.io/
✅ Zéro refactor global : uniquement ce job.
✅ Fournit /jobs/publish-due/schema pour diagnostiquer.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


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
    raise RuntimeError("get_db introuvable. Ajuste l'import dans routes/jobs_publish_due.py (_get_db_dep).")


get_db = _get_db_dep()

router = APIRouter(prefix="/jobs", tags=["Jobs • Publisher"])

GRAPH = "https://graph.facebook.com"
GRAPH_V = "v20.0"

DEFAULT_LINK = "https://legenerateurdigital.systeme.io/"


def _table_exists(db: Session, table_name: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name=:t
            LIMIT 1
            """
        ),
        {"t": table_name},
    ).first()
    return bool(row)


def _table_columns(db: Session, table_name: str) -> Set[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:t
            ORDER BY ordinal_position
            """
        ),
        {"t": table_name},
    ).all()
    return {str(r[0]) for r in rows}


def _pick_col(cols: Set[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    lc = {c.lower(): c for c in cols}
    for c in candidates:
        hit = lc.get(c.lower())
        if hit:
            return hit
    return None


def _detect_posts_table(db: Session) -> str:
    candidates = ["social_posts", "social_post", "planner_posts", "planner_post", "scheduled_posts", "posts"]
    for t in candidates:
        if _table_exists(db, t):
            return t
    raise HTTPException(status_code=500, detail="Aucune table de posts trouvée (social_posts/social_post/planner_posts...).")


def _ensure_lgd_connections_table(db: Session) -> None:
    db.execute(
        text(
            """
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
            """
        )
    )
    db.commit()


def _upsert_lgd_connection(
    db: Session,
    user_id: int,
    provider: str,
    page_id: Optional[str] = None,
    page_name: Optional[str] = None,
    page_access_token: Optional[str] = None,
    user_access_token: Optional[str] = None,
) -> None:
    _ensure_lgd_connections_table(db)
    db.execute(
        text(
            """
            INSERT INTO lgd_social_connections
              (user_id, provider, page_id, page_name, page_access_token, user_access_token, updated_at)
            VALUES
              (:user_id, :provider, :page_id, :page_name, :page_access_token, :user_access_token, NOW())
            ON CONFLICT (user_id, provider)
            DO UPDATE SET
              page_id = COALESCE(EXCLUDED.page_id, lgd_social_connections.page_id),
              page_name = COALESCE(EXCLUDED.page_name, lgd_social_connections.page_name),
              page_access_token = COALESCE(EXCLUDED.page_access_token, lgd_social_connections.page_access_token),
              user_access_token = COALESCE(EXCLUDED.user_access_token, lgd_social_connections.user_access_token),
              updated_at = NOW();
            """
        ),
        {
            "user_id": int(user_id),
            "provider": provider,
            "page_id": page_id,
            "page_name": page_name,
            "page_access_token": page_access_token,
            "user_access_token": user_access_token,
        },
    )
    db.commit()


def _get_lgd_fb_page_token(db: Session, user_id: int) -> Optional[dict]:
    _ensure_lgd_connections_table(db)
    row = db.execute(
        text(
            """
            SELECT page_id, page_access_token, page_name, user_access_token
            FROM lgd_social_connections
            WHERE user_id=:uid AND provider='facebook'
            LIMIT 1
            """
        ),
        {"uid": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def _get_social_connections_user_token(db: Session, user_id: int) -> Optional[str]:
    if not _table_exists(db, "social_connections"):
        return None
    cols = _table_columns(db, "social_connections")
    if "access_token" not in cols or "network" not in cols or "user_id" not in cols:
        return None

    is_active_col = "is_active" if "is_active" in cols else None
    where_active = ""
    if is_active_col:
        where_active = f" AND {is_active_col}=TRUE"

    row = db.execute(
        text(
            f"""
            SELECT access_token
            FROM social_connections
            WHERE user_id=:uid AND network='facebook'
            {where_active}
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"uid": int(user_id)},
    ).first()
    if not row:
        return None
    token = str(row[0] or "").strip()
    return token or None


def _fb_publish_page_post(page_id: str, page_token: str, message: str, link: Optional[str]) -> dict:
    payload: Dict[str, Any] = {"message": message, "access_token": page_token}
    if link:
        payload["link"] = link

    r = requests.post(f"{GRAPH}/{GRAPH_V}/{page_id}/feed", data=payload, timeout=25)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook publish error: {j}")
    return r.json()


def _fb_get_first_page_from_user_token(user_token: str) -> Tuple[str, str, str]:
    r = requests.get(
        f"{GRAPH}/{GRAPH_V}/me/accounts",
        params={"access_token": user_token, "fields": "id,name,access_token"},
        timeout=25,
    )
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Facebook API error (me/accounts): {j}")

    data = (r.json() or {}).get("data") or []
    if not data:
        raise HTTPException(status_code=400, detail="Aucune page trouvée sur ce token Facebook (me/accounts vide).")

    first = data[0] or {}
    page_id = str(first.get("id") or "").strip()
    page_name = str(first.get("name") or "").strip()
    page_token = str(first.get("access_token") or "").strip()
    if not page_id or not page_token:
        raise HTTPException(status_code=400, detail="Page invalide (id/token manquants) depuis me/accounts.")
    return page_id, page_name, page_token


def _resolve_posts_mapping(db: Session) -> Dict[str, str]:
    table = _detect_posts_table(db)
    cols = _table_columns(db, table)

    mapping: Dict[str, Optional[str]] = {
        "table": table,
        "id": _pick_col(cols, ["id"]),
        "user": _pick_col(cols, ["user_id", "owner_id", "created_by", "author_id", "uid"]),
        "network": _pick_col(cols, ["network", "reseau", "réseau", "provider", "platform", "social_network"]),
        "status": _pick_col(cols, ["status", "statut", "etat", "état", "state", "publish_status"]),
        "scheduled": _pick_col(cols, ["scheduled_at", "scheduled_for", "publish_at", "planned_at", "run_at", "date_programmee", "date_programmée"]),
        "text": _pick_col(cols, ["content_text", "content", "contenu", "texte", "text", "caption", "message", "body"]),
        "link": _pick_col(cols, ["content_link", "link", "url", "target_url"]),
        "statut": _pick_col(cols, ["statut"]),
    }

    required = ["id", "user", "network", "status", "scheduled", "text"]
    missing = [k for k in required if not mapping.get(k)]
    if missing:
        cols_list = ", ".join(sorted(cols))
        raise HTTPException(
            status_code=500,
            detail=f"Schéma {table} incompatible. Colonnes manquantes: {', '.join(missing)}. Colonnes trouvées: {cols_list}",
        )

    out: Dict[str, str] = {k: str(v) for k, v in mapping.items() if v is not None}
    if "link" not in out:
        out["link"] = ""
    if "statut" not in out:
        out["statut"] = ""
    return out


def _resolve_update_columns(db: Session, table: str) -> Dict[str, str]:
    cols = _table_columns(db, table)
    published_at = _pick_col(cols, ["published_at", "posted_at"])
    external_id = _pick_col(cols, ["external_id", "provider_post_id", "post_id"])
    last_error = _pick_col(cols, ["last_error", "error", "error_message"])
    statut = _pick_col(cols, ["statut"])
    return {
        "published_at": str(published_at or ""),
        "external_id": str(external_id or ""),
        "last_error": str(last_error or ""),
        "statut": str(statut or ""),
    }


@router.get("/publish-due/schema")
def publish_due_schema(db: Session = Depends(get_db)):
    table = _detect_posts_table(db)
    cols = sorted(list(_table_columns(db, table)))
    try:
        mapping = _resolve_posts_mapping(db)
        upd = _resolve_update_columns(db, table)
        ok = True
        err = None
    except Exception as e:
        ok = False
        mapping = {"table": table}
        upd = {"published_at": "", "external_id": "", "last_error": "", "statut": ""}
        err = str(e)

    return {
        "ok": ok,
        "posts": {
            "table": table,
            "columns": cols,
            "mapping": mapping,
            "update_columns": upd,
        },
        "connections": {
            "tables_found": [t for t in ["lgd_social_connections", "social_connections"] if _table_exists(db, t)],
        },
        "error": err,
    }


@router.post("/publish-due")
def publish_due(db: Session = Depends(get_db), limit: int = 25, network: str = "facebook"):
    network = str(network or "facebook").strip().lower()
    limit = max(1, min(int(limit or 25), 200))

    if network != "facebook":
        return {
            "ok": True,
            "processed": 0,
            "published": 0,
            "failed": 0,
            "items": [{"status": "skipped", "network": network, "error": f"Publisher not implemented for network '{network}'"}],
        }

    m = _resolve_posts_mapping(db)
    table = m["table"]
    upd = _resolve_update_columns(db, table)

    link_select = f", {m['link']} AS content_link" if m.get("link") else ", NULL::text AS content_link"

    sql_fetch = f"""
    SELECT
      {m['id']} AS id,
      {m['user']} AS user_id,
      {m['scheduled']} AS scheduled_at,
      {m['text']} AS content_text
      {link_select}
    FROM {table}
    WHERE {m['network']}=:network
      AND {m['status']}='scheduled'
      AND {m['scheduled']} <= NOW()
    ORDER BY {m['scheduled']} ASC
    LIMIT :limit;
    """

    rows = db.execute(text(sql_fetch), {"limit": limit, "network": network}).mappings().all()
    posts = [dict(r) for r in rows]
    if not posts:
        return {"ok": True, "processed": 0, "published": 0, "failed": 0, "items": []}

    published_set: List[str] = [f"{m['status']}='published'"]
    failed_set: List[str] = [f"{m['status']}='failed'"]

    if upd.get("statut"):
        published_set.append(f"{upd['statut']}='published'")
        failed_set.append(f"{upd['statut']}='failed'")

    if upd["published_at"]:
        published_set.append(f"{upd['published_at']}=NOW()")
    if upd["external_id"]:
        published_set.append(f"{upd['external_id']}=:external_id")
    if upd["last_error"]:
        published_set.append(f"{upd['last_error']}=NULL")
        failed_set.append(f"{upd['last_error']}=:err")

    sql_mark_published = f"UPDATE {table} SET {', '.join(published_set)} WHERE {m['id']}=:id;"
    sql_mark_failed = f"UPDATE {table} SET {', '.join(failed_set)} WHERE {m['id']}=:id;"

    published = 0
    failed = 0
    items: List[Dict[str, Any]] = []

    for p in posts:
        post_id = int(p["id"])
        user_id = int(p["user_id"])
        message = str(p.get("content_text") or "").strip()
        link_db = str(p.get("content_link") or "").strip()
        link = link_db or DEFAULT_LINK

        if not message:
            failed += 1
            db.execute(text(sql_mark_failed), {"id": post_id, "err": "Empty content"})
            db.commit()
            items.append({"id": post_id, "status": "failed", "error": "Empty content"})
            continue

        conn = _get_lgd_fb_page_token(db, user_id) or {}
        page_id = str(conn.get("page_id") or "").strip()
        page_token = str(conn.get("page_access_token") or "").strip()

        debug_conn: Dict[str, Any] = {"source": "lgd_social_connections", "page_id_present": bool(page_id), "page_token_len": len(page_token or "")}

        if not page_id or not page_token:
            user_token = _get_social_connections_user_token(db, user_id)
            debug_conn = {"source": "social_connections", "has_user_token": bool(user_token), "page_id_present": False, "page_token_len": 0}
            if user_token:
                try:
                    page_id, page_name, page_token = _fb_get_first_page_from_user_token(user_token)
                    _upsert_lgd_connection(
                        db=db,
                        user_id=user_id,
                        provider="facebook",
                        page_id=page_id,
                        page_name=page_name,
                        page_access_token=page_token,
                        user_access_token=user_token,
                    )
                    debug_conn = {"source": "social_connections->me/accounts", "page_id_present": True, "page_token_len": len(page_token or "")}
                except Exception as e:
                    debug_conn["error"] = str(e)

        if not page_id or not page_token:
            failed += 1
            db.execute(text(sql_mark_failed), {"id": post_id, "err": "Facebook page not connected"})
            db.commit()
            items.append({"id": post_id, "status": "failed", "error": "Facebook page not connected", "debug": debug_conn})
            continue

        try:
            out = _fb_publish_page_post(page_id=page_id, page_token=page_token, message=message, link=link)
            external_id = str(out.get("id") or "")
            db.execute(text(sql_mark_published), {"id": post_id, "external_id": external_id})
            db.commit()
            published += 1
            items.append({"id": post_id, "status": "published", "external_id": external_id, "page_id": page_id})
        except Exception as e:
            failed += 1
            db.execute(text(sql_mark_failed), {"id": post_id, "err": str(e)})
            db.commit()
            items.append({"id": post_id, "status": "failed", "error": str(e), "page_id": page_id})

    return {"ok": True, "processed": len(posts), "published": published, "failed": failed, "items": items}
