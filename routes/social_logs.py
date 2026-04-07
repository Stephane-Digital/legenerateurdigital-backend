from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from models.social_post_log import SocialPostLog
from schemas.social_post_schema import SocialPostLogResponse

router = APIRouter(prefix="/social-logs", tags=["Social Logs"])


def _normalize_network(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    v = str(value).strip().lower()

    if not v:
        return None

    if v in {"fb", "facebook"}:
        return "facebook"

    if v in {"ig", "instagram"}:
        return "instagram"

    if v in {"li", "linkedin", "linked_in"}:
        return "linkedin"

    return v


@router.get("/", response_model=List[SocialPostLogResponse])
def list_social_logs(
    network: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user["id"] if isinstance(user, dict) else user.id

    query = db.query(SocialPostLog).filter(
        SocialPostLog.user_id == user_id
    )

    normalized_network = _normalize_network(network)

    if normalized_network:
        query = query.filter(
            SocialPostLog.network == normalized_network
        )

    return (
        query.order_by(
            SocialPostLog.created_at.desc().nullslast()
        ).all()
    )
