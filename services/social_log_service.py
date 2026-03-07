from sqlalchemy.orm import Session
from models.social_post_log import SocialPostLog


def get_logs_for_user(db: Session, user_id: int):
    return db.query(SocialPostLog).filter(
        SocialPostLog.user_id == user_id
    ).order_by(SocialPostLog.created_at.desc()).all()
