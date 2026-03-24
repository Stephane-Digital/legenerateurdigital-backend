from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from models.user_model import User

router = APIRouter(prefix="/library", tags=["Library"])

# ---------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------

UPLOADS_DIR = Path("uploads") / "library"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------

def _guess_kind(filename: str, mime: Optional[str]) -> str:
    name = (filename or "").lower()
    if name.startswith("lgd_preview__"):
        return "preview"
    if name.endswith(".json"):
        if "post" in name:
            return "lgd_post_v5"
        if "carrousel" in name:
            return "lgd_carrousel_v5"
        return "json"
    if name.endswith(".html") or (mime or "").startswith("text/html"):
        return "html"
    if (mime or "").startswith("image/") or any(
        name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]
    ):
        return "image"
    if (mime or "").startswith("text/"):
        return "text"
    return "other"


def _abs_path_from_file_url(file_url: str) -> Path:
    p = (file_url or "").lstrip("/")
    return Path(p)


def _safe_read_json(path: Path) -> Optional[Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _table_exists(db: Session, table_name: str) -> bool:
    q = text(
        "SELECT EXISTS ("
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_name = :table_name"
        ")"
    )
    return bool(db.execute(q, {"table_name": table_name}).scalar())


def _table_columns(db: Session, table_name: str) -> Set[str]:
    q = text(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :table_name"
    )
    rows = db.execute(q, {"table_name": table_name}).fetchall()
    return {str(r[0]) for r in rows}


def _col_expr(cols: Set[str], name: str, alias: Optional[str] = None, cast: Optional[str] = None) -> str:
    final_alias = alias or name
    if name in cols:
        expr = name
        if cast:
            expr = f"{expr}::{cast}"
        return f"{expr} AS {final_alias}" if final_alias != name or cast else expr
    if cast:
        return f"NULL::{cast} AS {final_alias}"
    return f"NULL AS {final_alias}"


def _created_sort_expr(cols: Set[str]) -> str:
    if "created_at" in cols:
        return "created_at DESC NULLS LAST"
    if "updated_at" in cols:
        return "updated_at DESC NULLS LAST"
    if "id" in cols:
        return "id DESC"
    return "1"


# ---------------------------------------------------------------------
# DB helpers (tolerant to schema drift)
# ---------------------------------------------------------------------

def _row_to_item(row: Any) -> Dict[str, Any]:
    created = row.get("created_at")
    updated = row.get("updated_at")
    file_url = row.get("file_url") or ""

    item = {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "title": row.get("title") or "Sans titre",
        "description": row.get("description"),
        "file_url": file_url,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else (str(created) if created is not None else None),
        "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else (str(updated) if updated is not None else None),
    }

    item["preview_url"] = f"/library/file/{item['id']}"
    item["download_url"] = f"/library/download/{item['id']}"
    item["raw_url"] = f"/library/raw/{item['id']}"

    abs_path = _abs_path_from_file_url(file_url)
    if file_url and abs_path.exists():
        item["size"] = abs_path.stat().st_size
        mime, _ = mimetypes.guess_type(str(abs_path))
        item["mime_type"] = mime or "application/octet-stream"
        item["filename"] = abs_path.name
        item["kind"] = _guess_kind(abs_path.name, item["mime_type"])
    else:
        item["size"] = None
        item["mime_type"] = None
        item["filename"] = abs_path.name if file_url else None
        item["kind"] = _guess_kind(file_url, None)

    return item


def _db_list_items(db: Session, user_id: int) -> List[Dict[str, Any]]:
    if not _table_exists(db, "library_items"):
        return []

    cols = _table_columns(db, "library_items")
    if not {"id", "user_id"}.issubset(cols):
        return []

    select_sql = ", ".join(
        [
            _col_expr(cols, "id"),
            _col_expr(cols, "user_id"),
            _col_expr(cols, "title", cast="text"),
            _col_expr(cols, "description", cast="text"),
            _col_expr(cols, "file_url", cast="text"),
            _col_expr(cols, "created_at", cast="timestamp", alias="created_at"),
            _col_expr(cols, "updated_at", cast="timestamp", alias="updated_at"),
        ]
    )
    q = text(
        f"SELECT {select_sql} "
        f"FROM library_items WHERE user_id = :uid "
        f"ORDER BY {_created_sort_expr(cols)}"
    )
    res = db.execute(q, {"uid": user_id}).mappings().all()
    return [_row_to_item(r) for r in res]


def _db_get_item(db: Session, user_id: int, item_id: int) -> Dict[str, Any]:
    if not _table_exists(db, "library_items"):
        raise HTTPException(status_code=404, detail="Item not found")

    cols = _table_columns(db, "library_items")
    if not {"id", "user_id"}.issubset(cols):
        raise HTTPException(status_code=404, detail="Item not found")

    select_sql = ", ".join(
        [
            _col_expr(cols, "id"),
            _col_expr(cols, "user_id"),
            _col_expr(cols, "title", cast="text"),
            _col_expr(cols, "description", cast="text"),
            _col_expr(cols, "file_url", cast="text"),
            _col_expr(cols, "created_at", cast="timestamp", alias="created_at"),
            _col_expr(cols, "updated_at", cast="timestamp", alias="updated_at"),
        ]
    )
    q = text(
        f"SELECT {select_sql} "
        f"FROM library_items WHERE id = :id AND user_id = :uid"
    )
    row = db.execute(q, {"id": item_id, "uid": user_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return _row_to_item(row)


def _db_insert_item(db: Session, user_id: int, title: str, description: Optional[str], file_url: str) -> Dict[str, Any]:
    if not _table_exists(db, "library_items"):
        raise HTTPException(status_code=500, detail="Table library_items introuvable")

    cols = _table_columns(db, "library_items")
    if not {"id", "user_id"}.issubset(cols):
        raise HTTPException(status_code=500, detail="Schema library_items invalide")

    created_at = datetime.utcnow()

    insert_cols = ["user_id"]
    insert_vals = [":user_id"]
    params: Dict[str, Any] = {"user_id": user_id}

    if "title" in cols:
        insert_cols.append("title")
        insert_vals.append(":title")
        params["title"] = title or "Sans titre"

    if "description" in cols:
        insert_cols.append("description")
        insert_vals.append(":description")
        params["description"] = description

    if "file_url" in cols:
        insert_cols.append("file_url")
        insert_vals.append(":file_url")
        params["file_url"] = file_url
    else:
        raise HTTPException(status_code=500, detail="Colonne file_url introuvable")

    if "created_at" in cols:
        insert_cols.append("created_at")
        insert_vals.append(":created_at")
        params["created_at"] = created_at

    if "updated_at" in cols:
        insert_cols.append("updated_at")
        insert_vals.append(":updated_at")
        params["updated_at"] = created_at

    returning_sql = ", ".join(
        [
            _col_expr(cols, "id"),
            _col_expr(cols, "user_id"),
            _col_expr(cols, "title", cast="text"),
            _col_expr(cols, "description", cast="text"),
            _col_expr(cols, "file_url", cast="text"),
            _col_expr(cols, "created_at", cast="timestamp", alias="created_at"),
            _col_expr(cols, "updated_at", cast="timestamp", alias="updated_at"),
        ]
    )

    q = text(
        f"INSERT INTO library_items ({', '.join(insert_cols)}) "
        f"VALUES ({', '.join(insert_vals)}) "
        f"RETURNING {returning_sql}"
    )
    row = db.execute(q, params).mappings().first()
    db.commit()
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")
    return _row_to_item(row)


def _db_delete_item(db: Session, user_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    try:
        item = _db_get_item(db, user_id, item_id)
    except HTTPException:
        return None

    if not _table_exists(db, "library_items"):
        return None

    q = text("DELETE FROM library_items WHERE id = :id AND user_id = :uid")
    db.execute(q, {"id": item_id, "uid": user_id})
    db.commit()
    return item


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

@router.get("")
def list_library_root(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _db_list_items(db, current_user.id)


@router.get("/list")
def list_library(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _db_list_items(db, current_user.id)


@router.get("/items")
def list_library_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _db_list_items(db, current_user.id)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file:
        raise HTTPException(status_code=400, detail="No file")

    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.split(".")[-1].lower()

    if not ext and file.content_type:
        guessed = mimetypes.guess_extension(file.content_type) or ""
        ext = guessed

    safe_title = title or (file.filename or "Fichier")
    import uuid

    token = uuid.uuid4().hex
    stored_name = f"{_guess_kind(file.filename or '', file.content_type)}__{token}{ext}"
    dest = UPLOADS_DIR / stored_name

    content = await file.read()
    dest.write_bytes(content)

    file_url = f"/uploads/library/{stored_name}"
    item = _db_insert_item(db, current_user.id, safe_title, description, file_url)
    return item


@router.post("")
async def save_draft_root(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await save_draft(payload=payload, db=db, current_user=current_user)


@router.post("/save-draft")
async def save_draft(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kind = (payload.get("kind") or "json").strip()
    title = (payload.get("title") or f"Draft — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}").strip()
    data = payload.get("data")

    if data is None:
        raise HTTPException(status_code=400, detail="Missing data")

    import uuid

    token = uuid.uuid4().hex
    stored_name = f"{kind}__{token}.json"
    dest = UPLOADS_DIR / stored_name
    dest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    file_url = f"/uploads/library/{stored_name}"
    item = _db_insert_item(db, current_user.id, title, None, file_url)
    return item


@router.post("/save-carrousel")
async def save_carrousel_legacy(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid

    token = uuid.uuid4().hex
    stored_name = f"lgd_carrousel_v5__{token}.json"
    dest = UPLOADS_DIR / stored_name
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    file_url = f"/uploads/library/{stored_name}"
    title = f"Carrousel — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    item = _db_insert_item(db, current_user.id, title, None, file_url)
    return item


@router.get("/raw/{item_id}")
def get_raw(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _db_get_item(db, current_user.id, item_id)
    abs_path = _abs_path_from_file_url(item["file_url"])
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    mime, _ = mimetypes.guess_type(str(abs_path))
    mime = mime or "application/octet-stream"

    if abs_path.suffix.lower() == ".json":
        parsed = _safe_read_json(abs_path)
        if parsed is not None:
            return JSONResponse(parsed)
        return JSONResponse({"raw": abs_path.read_text(encoding="utf-8", errors="ignore")})

    if mime.startswith("text/") or abs_path.suffix.lower() in [".txt", ".md", ".csv", ".html"]:
        return JSONResponse({"raw": abs_path.read_text(encoding="utf-8", errors="ignore")})

    return JSONResponse({"detail": "binary", "mime_type": mime, "size": abs_path.stat().st_size})


@router.get("/file/{item_id}")
def preview_file(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _db_get_item(db, current_user.id, item_id)
    abs_path = _abs_path_from_file_url(item["file_url"])
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    mime, _ = mimetypes.guess_type(str(abs_path))
    return FileResponse(path=str(abs_path), media_type=mime or "application/octet-stream")


@router.get("/download/{item_id}")
def download_file(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _db_get_item(db, current_user.id, item_id)
    abs_path = _abs_path_from_file_url(item["file_url"])
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    mime, _ = mimetypes.guess_type(str(abs_path))
    filename = item.get("filename") or abs_path.name
    return FileResponse(path=str(abs_path), media_type=mime or "application/octet-stream", filename=filename)


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _db_delete_item(db, current_user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        abs_path = _abs_path_from_file_url(item["file_url"])
        if abs_path.exists():
            abs_path.unlink()
    except Exception:
        pass

    return {"ok": True}


@router.delete("/items/{item_id}")
def delete_item_legacy(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_item(item_id=item_id, db=db, current_user=current_user)
