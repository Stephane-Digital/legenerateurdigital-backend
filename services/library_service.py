from sqlalchemy.orm import Session
from models.library_item_model import LibraryItem
from schemas.library_schema import LibraryItemCreate, LibraryItemUpdate


def create_item(db: Session, user_id: int, payload: LibraryItemCreate):
    item = LibraryItem(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        file_url=payload.file_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: LibraryItem, payload: LibraryItemUpdate):
    for f, v in payload.dict(exclude_unset=True).items():
        setattr(item, f, v)

    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: LibraryItem):
    db.delete(item)
    db.commit()
