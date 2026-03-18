from sqlalchemy.orm import Session
from models.slide_library_model import SlideLibraryItem
from schemas.slide_schema import SlideLibraryCreate


def save_slide_to_library(db: Session, user_id: int, payload: SlideLibraryCreate):
    item = SlideLibraryItem(
        user_id=user_id,
        name=payload.name,
        category=payload.category,
        data=payload.data
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_library_slides(db: Session, user_id: int):
    return db.query(SlideLibraryItem).filter(SlideLibraryItem.user_id == user_id).all()
