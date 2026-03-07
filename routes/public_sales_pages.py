from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.sales_page_service import get_public_sales_page

router = APIRouter(
    prefix="/public/sales-pages",
    tags=["Public Sales Pages"],
)


@router.get("/{page_id}")
def get_public_page(page_id: int, db: Session = Depends(get_db)):
    """
    Récupère une page de vente PUBLIC (sans authentification).

    Retourne toujours un objet du type :
    {
        "id": int,
        "title": str,
        "subtitle": str | null,
        "blocks": [ ... ],
        "created_at": "2025-11-18T23:00:48.348162"
    }
    """
    page = get_public_sales_page(db, page_id)

    if not page:
        raise HTTPException(status_code=404, detail="Page introuvable.")

    return page
