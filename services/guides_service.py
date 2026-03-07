from sqlalchemy.orm import Session
from models.guide_model import Guide
from schemas.guide_schema import GuideCreate, GuideUpdate


def create_guide(db: Session, payload: GuideCreate):
    guide = Guide(
        title=payload.title,
        description=payload.description,
        content=payload.content,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


def update_guide(db: Session, guide: Guide, payload: GuideUpdate):
    for f, v in payload.dict(exclude_unset=True).items():
        setattr(guide, f, v)

    db.commit()
    db.refresh(guide)
    return guide
