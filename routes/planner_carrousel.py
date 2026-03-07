from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/planner/carrousel", tags=["Planner Carrousel"])


@router.post("/assign")
def assign_carrousel_to_date(carrousel_id: int, date: str, time: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Ici tu vas relier à la table de ton Planner existante
    # Je laisse hook prêt :
    return {
        "status": "scheduled",
        "carrousel_id": carrousel_id,
        "date": date,
        "time": time,
        "user_id": user.id
    }
