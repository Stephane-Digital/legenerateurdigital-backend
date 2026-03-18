from __future__ import annotations

"""
LGD — Jobs Publisher (Facebook + Instagram)
-------------------------------------------
Publie automatiquement les posts "dus" (scheduled_at <= NOW()).

Objectif (PROPRE + ROBUSTE) :
✅ Compatible schéma FR : reseau / date_programmee / contenu / status (+ statut optionnel)
✅ Compatible schéma EN : network / scheduled_at / content_text / status
✅ Facebook :
   - Priorité : lgd_social_connections (page_id + page_access_token)
   - Fallback : social_connections (network='facebook' + access_token) = user token
     => récupère /me/accounts, prend la 1ère page, stocke page_id + page_access_token dans lgd_social_connections
✅ Instagram :
   - Utilise social_connections (network='instagram')
   - page_id = instagram_business_account.id
   - access_token = long-lived token
   - Support post image simple + carrousel
✅ Fallback LINK si pas de link DB : https://legenerateurdigital.systeme.io/
✅ Zéro refactor global : uniquement ce job.
✅ Fournit /jobs/publish-due/schema pour diagnostiquer.
"""

import json
from datetime import datetime
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
GRAPH_V = "v25.0"

DEFAULT_LINK = "https://legenerateurdigital.systeme.io/"


def _safe_json_loads(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            return value
    return value


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


def _get_social_connections_row(db: Session, user_id: int, network: str) -> Optional[Dict[str, Any]]:
    if not _table_exists(db, "social_connections"):
        return None
    cols = _table_columns(db, "social_connections")
    needed = {"user_id", "network", "access_token"}
    if not needed.issubset(cols):
        return None

    has_page_id = "page_id" in cols
    has_page_name = "page_name" in cols
    has_page_access_token = "page_access_token" in cols
    has_expires_at = "expires_at" in cols
    is_active_col = "is_active" if "is_active" in cols else None

    where_active = f" AND {is_active_col}=TRUE" if is_active_col else ""

    sql = f"""
        SELECT
          access_token,
          {('page_id' if has_page_id else 'NULL')} AS page_id,
          {('page_name' if has_page_name else 'NULL')} AS page_name,
          {('page_access_token' if has_page_access_token else 'NULL')} AS page_access_token,
          {('expires_at' if has_expires_at else 'NULL')} AS expires_at
        FROM social_connections
        WHERE user_id=:uid AND network=:network
        {where_active}
        ORDER BY id DESC
        LIMIT 1
    """
    row = db.execute(text(sql), {"uid": int(user_id), "network": str(network)}).mappings().first()
    return dict(row) if row else None


def _get_social_connections_user_token(db: Session, user_id: int) -> Optional[str]:
    row = _get_social_connections_row(db, user_id, "facebook")
    if not row:
        return None
    token = str(row.get("access_token") or "").strip()
    return token or None


def _get_instagram_connection(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    row = _get_social_connections_row(db, user_id, "instagram")
    if not row:
        return None
    return {
        "ig_user_id": str(row.get("page_id") or "").strip(),
        "ig_username": str(row.get("page_name") or "").strip(),
        "access_token": str(row.get("access_token") or "").strip(),
        "expires_at": row.get("expires_at"),
    }


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


def _extract_message_and_payload(content_text: Any) -> Tuple[str, Dict[str, Any]]:
    raw = _safe_json_loads(content_text)
    if isinstance(raw, dict):
        message = str(raw.get("caption") or raw.get("text") or raw.get("message") or raw.get("titre") or raw.get("title") or "").strip()
        return message, raw
    text_value = str(content_text or "").strip()
    return text_value, {"type": "post", "caption": text_value}


def _normalize_image_url(slide: Any) -> str:
    if isinstance(slide, str):
        return slide.strip()
    if isinstance(slide, dict):
        for key in ["media_url", "image_url", "url", "src", "image", "preview_url"]:
            value = str(slide.get(key) or "").strip()
            if value:
                return value
    return ""


def _resolve_instagram_media(payload: Dict[str, Any], link_fallback: str) -> Dict[str, Any]:
    kind = str(payload.get("type") or payload.get("kind") or payload.get("format") or "post").strip().lower()
    caption = str(payload.get("caption") or payload.get("text") or payload.get("message") or payload.get("titre") or payload.get("title") or "").strip()

    media_url = ""
    for key in ["media_url", "image_url", "url", "image", "preview_url"]:
        media_url = str(payload.get(key) or "").strip()
        if media_url:
            break

    slides_raw = payload.get("slides") or payload.get("items") or payload.get("images") or []
    slides: List[Dict[str, str]] = []
    if isinstance(slides_raw, list):
        for item in slides_raw:
            slide_url = _normalize_image_url(item)
            if slide_url:
                slides.append({"media_url": slide_url})

    if kind in {"carrousel", "carousel"}:
        if not slides:
            if media_url:
                slides = [{"media_url": media_url}]
            else:
                raise HTTPException(status_code=400, detail="Instagram carrousel invalide: aucune slide exploitable.")
        return {"type": "carrousel", "caption": caption, "slides": slides}

    if not media_url and slides:
        media_url = slides[0]["media_url"]
    if not media_url:
        media_url = link_fallback
    return {"type": "post", "caption": caption, "media_url": media_url}


def _ig_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{GRAPH}/{GRAPH_V}{path}", data=payload, timeout=40)
    if not r.ok:
        try:
            j = r.json()
        except Exception:
            j = {"error": {"message": r.text}}
        raise HTTPException(status_code=400, detail=f"Instagram publish error: {j}")
    return r.json()


def _ig_create_media_container(ig_user_id: str, token: str, image_url: str, caption: str = "", is_carousel_item: bool = False) -> str:
    payload: Dict[str, Any] = {
        "image_url": image_url,
        "access_token": token,
    }
    if caption and not is_carousel_item:
        payload["caption"] = caption
    if is_carousel_item:
        payload["is_carousel_item"] = "true"

    out = _ig_post(f"/{ig_user_id}/media", payload)
    creation_id = str(out.get("id") or "").strip()
    if not creation_id:
        raise HTTPException(status_code=400, detail="Instagram media container id manquant.")
    return creation_id


def _ig_publish_media_container(ig_user_id: str, token: str, creation_id: str) -> Dict[str, Any]:
    return _ig_post(
        f"/{ig_user_id}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": token,
        },
    )


def _ig_publish_single_image(ig_user_id: str, token: str, caption: str, image_url: str) -> Dict[str, Any]:
    creation_id = _ig_create_media_container(ig_user_id=ig_user_id, token=token, image_url=image_url, caption=caption)
    return _ig_publish_media_container(ig_user_id=ig_user_id, token=token, creation_id=creation_id)


def _ig_publish_carrousel(ig_user_id: str, token: str, caption: str, slides: List[Dict[str, str]]) -> Dict[str, Any]:
    children: List[str] = []
    for slide in slides:
        slide_url = str(slide.get("media_url") or "").strip()
        if not slide_url:
            continue
        child_id = _ig_create_media_container(
            ig_user_id=ig_user_id,
            token=token,
            image_url=slide_url,
            caption="",
            is_carousel_item=True,
        )
        children.append(child_id)

    if not children:
        raise HTTPException(status_code=400, detail="Instagram carrousel invalide: aucun child container généré.")

    out = _ig_post(
        f"/{ig_user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        },
    )
    creation_id = str(out.get("id") or "").strip()
    if not creation_id:
        raise HTTPException(status_code=400, detail="Instagram parent carousel creation id manquant.")
    return _ig_publish_media_container(ig_user_id=ig_user_id, token=token, creation_id=creation_id)


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

    supported_networks = {"facebook", "instagram"}
    if network not in supported_networks:
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
        raw_content = p.get("content_text")
        link_db = str(p.get("content_link") or "").strip()
        link = link_db or DEFAULT_LINK

        message, payload = _extract_message_and_payload(raw_content)

        try:
            if network == "facebook":
                if not message:
                    raise HTTPException(status_code=400, detail="Empty content")

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
                    raise HTTPException(status_code=400, detail=f"Facebook page not connected | debug={debug_conn}")

                out = _fb_publish_page_post(page_id=page_id, page_token=page_token, message=message, link=link)
                external_id = str(out.get("id") or "")
                db.execute(text(sql_mark_published), {"id": post_id, "external_id": external_id})
                db.commit()
                published += 1
                items.append({"id": post_id, "status": "published", "external_id": external_id, "page_id": page_id})
                continue

            if network == "instagram":
                conn = _get_instagram_connection(db, user_id) or {}
                ig_user_id = str(conn.get("ig_user_id") or "").strip()
                ig_username = str(conn.get("ig_username") or "").strip()
                ig_token = str(conn.get("access_token") or "").strip()

                if not ig_user_id or not ig_token:
                    raise HTTPException(status_code=400, detail="Instagram account not connected")

                normalized = _resolve_instagram_media(payload, link)
                if normalized["type"] == "carrousel":
                    out = _ig_publish_carrousel(
                        ig_user_id=ig_user_id,
                        token=ig_token,
                        caption=str(normalized.get("caption") or ""),
                        slides=normalized.get("slides") or [],
                    )
                else:
                    out = _ig_publish_single_image(
                        ig_user_id=ig_user_id,
                        token=ig_token,
                        caption=str(normalized.get("caption") or ""),
                        image_url=str(normalized.get("media_url") or ""),
                    )

                external_id = str(out.get("id") or out.get("post_id") or "")
                db.execute(text(sql_mark_published), {"id": post_id, "external_id": external_id})
                db.commit()
                published += 1
                items.append({
                    "id": post_id,
                    "status": "published",
                    "external_id": external_id,
                    "ig_user_id": ig_user_id,
                    "ig_username": ig_username,
                    "published_type": normalized["type"],
                })
                continue

        except Exception as e:
            failed += 1
            db.execute(text(sql_mark_failed), {"id": post_id, "err": str(e)})
            db.commit()
            items.append({"id": post_id, "status": "failed", "error": str(e), "network": network})

    return {"ok": True, "processed": len(posts), "published": published, "failed": failed, "items": items}
