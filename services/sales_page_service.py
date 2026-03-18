from sqlalchemy.orm import Session
from models.sales_page_model import SalesPage
from schemas.sales_page_schema import (
    SalesPageCreateSchema,
    SalesPageUpdateSchema,
)


# ============================================================
# 📝 CREATE SALES PAGE (service)
# ============================================================
def create_sales_page(db: Session, user_id: int, payload: SalesPageCreateSchema):
    page = SalesPage(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        generated_content=payload.generated_content,
    )

    db.add(page)
    db.commit()
    db.refresh(page)

    return page


# ============================================================
# 📝 UPDATE SALES PAGE (service)
# ============================================================
def update_sales_page(db: Session, page: SalesPage, payload: SalesPageUpdateSchema):
    if payload.title is not None:
        page.title = payload.title
    if payload.description is not None:
        page.description = payload.description
    if payload.generated_content is not None:
        page.generated_content = payload.generated_content

    db.commit()
    db.refresh(page)

    return page


# ============================================================
# 🌍 PUBLIC SALES PAGE (service)
# ============================================================
def get_public_sales_page(db: Session, page_id: int):
    page = db.query(SalesPage).filter(SalesPage.id == page_id).first()

    if not page:
        return None

    return {
        "id": page.id,
        "title": page.title,
        "description": page.description,
        "generated_content": page.generated_content,
        "created_at": page.created_at,
    }
