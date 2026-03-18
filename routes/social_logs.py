from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from services.auth_service import get_current_user
from models.social_post_log import SocialPostLog
from schemas.social_post_schema import SocialPostLogResponse

router = APIRouter(prefix="/social-logs", tags=["Social Logs"])


@router.get("/", response_model=List[SocialPostLogResponse])
def list_social_logs(
    network: Optional[str] = None,
    db: Session = Depends(get_current_user),
    user=Depends(get_current_user)
):
    query = db.query(SocialPostLog).filter(SocialPostLog.user_id == user.id)

    if network:
        query = query.filter(SocialPostLog.network == network)

    logs = query.order_by(SocialPostLog.created_at.desc()).all()
    return logs
