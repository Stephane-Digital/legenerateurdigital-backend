# C:\LGD\legenerateurdigital_backend\routes\sales_pages.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from services.auth_service import get_current_user
from models.sales_page_model import SalesPage

from pydantic import BaseModel

router = APIRouter(
    prefix="/sales-pages",
    tags=["Sales Pages"]
)

# ============================================================
# 🟦 SCHÉMAS
# ============================================================

class SalesPageCreate(BaseModel):
    title: str
    description: str | None = None
    generated_content: str | None = None  # JSON string


class SalesPageUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    generated_content: str | None = None


# ============================================================
# 🟦 LISTER LES SALES PAGES
# ============================================================

@router.get("/", response_model=None)
def list_sales_pages(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pages = (
        db.query(SalesPage)
        .filter(SalesPage.user_id == current_user.id)
        .order_by(SalesPage.created_at.desc())
        .all()
    )

    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "created_at": p.created_at,
        }
        for p in pages
    ]


# ============================================================
# 🟦 CRÉER UNE SALES PAGE
# ============================================================

@router.post("/", response_model=None)
def create_sales_page(
    payload: SalesPageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_page = SalesPage(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        generated_content=payload.generated_content,
        created_at=datetime.utcnow()
    )

    db.add(new_page)
    db.commit()
    db.refresh(new_page)

    return {"message": "Page de vente créée", "id": new_page.id}


# ============================================================
# 🟦 OBTENIR UNE SALES PAGE
# ============================================================

@router.get("/{page_id}", response_model=None)
def get_sales_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    page = (
        db.query(SalesPage)
        .filter(
            SalesPage.id == page_id,
            SalesPage.user_id == current_user.id
        )
        .first()
    )

    if not page:
        raise HTTPException(status_code=404, detail="Page de vente introuvable")

    return {
        "id": page.id,
        "title": page.title,
        "description": page.description,
        "generated_content": page.generated_content,
        "created_at": page.created_at,
    }


# ============================================================
# 🟦 METTRE À JOUR UNE SALES PAGE
# ============================================================

@router.put("/{page_id}", response_model=None)
def update_sales_page(
    page_id: int,
    payload: SalesPageUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    page = (
        db.query(SalesPage)
        .filter(
            SalesPage.id == page_id,
            SalesPage.user_id == current_user.id
        )
        .first()
    )

    if not page:
        raise HTTPException(status_code=404, detail="Page de vente introuvable")

    if payload.title is not None:
        page.title = payload.title

    if payload.description is not None:
        page.description = payload.description

    if payload.generated_content is not None:
        page.generated_content = payload.generated_content

    db.commit()
    db.refresh(page)

    return {"message": "Page de vente mise à jour"}


# ============================================================
# 🟦 SUPPRIMER UNE SALES PAGE
# ============================================================

@router.delete("/{page_id}", response_model=None)
def delete_sales_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    page = (
        db.query(SalesPage)
        .filter(
            SalesPage.id == page_id,
            SalesPage.user_id == current_user.id
        )
        .first()
    )

    if not page:
        raise HTTPException(status_code=404, detail="Page de vente introuvable")

    db.delete(page)
    db.commit()

    return {"message": "Page de vente supprimée"}
