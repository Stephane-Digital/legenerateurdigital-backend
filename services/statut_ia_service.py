from sqlalchemy.orm import Session
from models.statut_ia_model import IAStatus


def get_ia_status(db: Session):
    """Retourne le statut IA (créé automatiquement si inexistant)"""

    status = db.query(IAStatus).first()

    if not status:
        status = IAStatus(
            status="online",
            available_tokens=1000,
            used_tokens=0
        )
        db.add(status)
        db.commit()
        db.refresh(status)

    return status


def update_ia_status(db: Session, new_status: str = None, used_tokens: int = None, available_tokens: int = None):
    """Met à jour le statut IA"""

    status = get_ia_status(db)

    if new_status:
        status.status = new_status

    if used_tokens is not None:
        status.used_tokens = used_tokens

    if available_tokens is not None:
        status.available_tokens = available_tokens

    db.commit()
    db.refresh(status)
    return status
