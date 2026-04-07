from fastapi import APIRouter, HTTPException
from services.make_dispatcher import send_to_make

router = APIRouter(prefix="/planner", tags=["Planner Make"])


@router.post("/posts/{post_id}/send-to-make")
async def send_post_to_make(post_id: int):
    try:
        fake_post = {
            "id": post_id,
            "network": "instagram",
            "content": "Test post LGD",
            "media": [],
            "scheduled_at": None,
        }

        result = send_to_make(fake_post)

        return {
            "success": True,
            "status": "sent_to_make",
            "result": result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/make/callback")
async def make_callback(payload: dict):
    status = payload.get("status", "unknown")
    post_id = payload.get("post_id")

    return {
        "success": True,
        "post_id": post_id,
        "status": status,
    }
