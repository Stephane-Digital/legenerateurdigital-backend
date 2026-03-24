from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _guess_kind(filename: str, mime: Optional[str]) -> str:
    name = (filename or "").lower()
    if name.startswith("lgd_preview__"):
        return "preview"
    if name.endswith(".json"):
        # drafts editor intelligent
        if "post" in name:
            return "lgd_post_v5"
        if "carrousel" in name:
            return "lgd_carrousel_v5"
        return "json"
    if name.endswith(".html") or (mime or "").startswith("text/html"):
        return "html"
    if (mime or "").startswith("image/") or any(name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
        return "image"
    if (mime or "").startswith("text/"):
        return "text"
    return "other"


def _abs_path_from_file_url(file_url: str) -> Path:
    # file_url is expected like "/uploads/library/xxx.ext" or "uploads/library/xxx.ext"
    p = file_url.lstrip("/")
    return Path(p)


def _safe_read_json(path: Path) -> Optional[Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------
# DB helpers (avoid relying on ORM columns that may not exist in DB)
# Table expected: library_items(id, user_id, title, description, file_url, created_at)
# ---------------------------------------------------------------------

def _row_to_item(row: Any) -> Dict[str, Any]:
    # row mapping from SQLAlchemy text result
    item = {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "title": row["title"],
        "description": row["description"],
        "file_url": row["file_url"],
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
    }

    # computed urls (do NOT depend on /uploads being mounted)
    item["preview_url"] = f"/library/file/{item['id']}"
    item["download_url"] = f"/library/download/{item['id']}"
    item["raw_url"] = f"/library/raw/{item['id']}"

    # computed meta
    abs_path = _abs_path_from_file_url(item["file_url"])
    if abs_path.exists():
        item["size"] = abs_path.stat().st_size
        mime, _ = mimetypes.guess_type(str(abs_path))
        item["mime_type"] = mime or "application/octet-stream"
        item["filename"] = abs_path.name
        item["kind"] = _guess_kind(abs_path.name, item["mime_type"])
    else:
        item["size"] = None
        item["mime_type"] = None
        item["filename"] = None
        item["kind"] = _guess_kind(item["file_url"], None)

    return item


def _db_list_items(db: Session, user_id: int) -> List[Dict[str, Any]]:
    q = text(
        "SELECT id, user_id, title, description, file_url, created_at "
        "FROM library_items WHERE user_id = :uid "
        "ORDER BY created_at DESC"
    )
    res = db.execute(q, {"uid": user_id}).mappings().all()
    return [_row_to_item(r) for r in res]


def _db_get_item(db: Session, user_id: int, item_id: int) -> Dict[str, Any]:
    q = text(
        "SELECT id, user_id, title, description, file_url, created_at "
        "FROM library_items WHERE id = :id AND user_id = :uid"
    )
    row = db.execute(q, {"id": item_id, "uid": user_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return _row_to_item(row)


def _db_insert_item(db: Session, user_id: int, title: str, description: Optional[str], file_url: str) -> Dict[str, Any]:
    q = text(
        "INSERT INTO library_items (user_id, title, description, file_url, created_at) "
        "VALUES (:user_id, :title, :description, :file_url, :created_at) "
        "RETURNING id, user_id, title, description, file_url, created_at"
    )
    created_at = datetime.utcnow()
    row = db.execute(
        q,
        {
            "user_id": user_id,
            "title": title,
            "description": description,
            "file_url": file_url,
            "created_at": created_at,
        },
    ).mappings().first()
    db.commit()
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")
    return _row_to_item(row)


def _db_delete_item(db: Session, user_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    # fetch first
    try:
        item = _db_get_item(db, user_id, item_id)
    except HTTPException:
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


# alias for older frontend calls
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

    # filename
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.split(".")[-1].lower()

    # normalize extension from content-type if missing
    if not ext and file.content_type:
        guessed = mimetypes.guess_extension(file.content_type) or ""
        ext = guessed

    safe_title = title or (file.filename or "Fichier")
    # store
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
    """
    Body example:
    {
      "kind": "lgd_post_v5" | "lgd_carrousel_v5",
      "title": "Post — Janvier",
      "data": {...}   // JSON to store
    }
    """
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
    """
    Legacy endpoint used by the editor intelligent.
    It stores the given payload as a JSON file and creates a library item.
    """
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
        # fallback
        return JSONResponse({"raw": abs_path.read_text(encoding="utf-8", errors="ignore")})

    if mime.startswith("text/") or abs_path.suffix.lower() in [".txt", ".md", ".csv", ".html"]:
        return JSONResponse({"raw": abs_path.read_text(encoding="utf-8", errors="ignore")})

    # binary: provide meta only
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


@router.delete("/items/{item_id}")
def delete_item_alias(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_item(item_id=item_id, db=db, current_user=current_user)


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _db_delete_item(db, current_user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # best-effort remove file
    try:
        abs_path = _abs_path_from_file_url(item["file_url"])
        if abs_path.exists():
            abs_path.unlink()
    except Exception:
        pass

    return {"ok": True}
