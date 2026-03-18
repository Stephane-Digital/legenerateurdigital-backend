
from fastapi import APIRouter, Request
from services.tracking.systeme_tracking_service import handle_systeme_event

router = APIRouter(prefix="/systeme-webhooks")

@router.post("/events")
async def systeme_webhook(request: Request):
    payload = await request.json()
    return handle_systeme_event(payload)
