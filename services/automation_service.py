from sqlalchemy.orm import Session
from models.automation_model import Automation
from schemas.automation_schema import AutomationCreate, AutomationUpdate


def get_user_automations(db: Session, user_id: int):
    return db.query(Automation).filter(Automation.user_id == user_id).all()


def get_automation_by_id(db: Session, automation_id: int, user_id: int):
    return db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.user_id == user_id
    ).first()


def create_automation(db: Session, data: AutomationCreate, user_id: int):
    new_auto = Automation(
        title=data.title,
        description=data.description,
        user_id=user_id
    )
    db.add(new_auto)
    db.commit()
    db.refresh(new_auto)
    return new_auto


def update_automation(db: Session, automation: Automation, data: AutomationUpdate):
    automation.title = data.title
    automation.description = data.description
    db.commit()
    db.refresh(automation)
    return automation


def delete_automation(db: Session, automation: Automation):
    db.delete(automation)
    db.commit()
    return True
