from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import get_current_user
from models.automation_model import Automation
from schemas.automation_schema import AutomationCreate, AutomationUpdate

router = APIRouter(prefix="/automatisations", tags=["Automatisations"])


@router.get("/")
def list_for_user(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Automation).filter(Automation.user_id == user.id).all()


@router.post("/")
def create(payload: AutomationCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    auto = Automation(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active
    )
    db.add(auto)
    db.commit()
    db.refresh(auto)
    return auto


@router.put("/{automation_id}")
def update(automation_id: int, payload: AutomationUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.user_id == user.id
    ).first()

    if not auto:
        raise HTTPException(404, "Automation introuvable")

    for f, v in payload.dict(exclude_unset=True).items():
        setattr(auto, f, v)

    db.commit()
    db.refresh(auto)
    return auto


@router.delete("/{automation_id}")
def delete(automation_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.user_id == user.id
    ).first()

    if not auto:
        raise HTTPException(404, "Automation introuvable")

    db.delete(auto)
    db.commit()
    return {"status": "deleted"}
