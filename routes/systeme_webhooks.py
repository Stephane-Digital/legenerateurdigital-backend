from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.integrations.systeme_subscription_service import apply_webhook_event
from services.tracking.systeme_tracking_service import handle_systeme_event

router = APIRouter(prefix="/systeme-webhooks")


@router.post("/events")
async def systeme_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    event_name = payload.get("event") or payload.get("type") or payload.get("name")

    try:
        result = apply_webhook_event(db, payload=payload, event_name=event_name)
        if result.get("status") != "ignored":
            return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()

    return handle_systeme_event(payload)
