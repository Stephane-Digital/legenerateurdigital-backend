from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from routes.auth import get_current_user
from schemas.slide_schema import SlideLibraryCreate
from services.slide_library_service import save_slide_to_library, list_library_slides

router = APIRouter(prefix="/carrousel/library", tags=["Slide Library"])


@router.post("/save")
def save_to_library(payload: SlideLibraryCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = save_slide_to_library(db, user.id, payload)
    return {"status": "success", "item": item}


@router.get("/list")
def list_library(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return list_library_slides(db, user.id)
