from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class SocialPostLog(Base):
    __tablename__ = "social_post_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("social_posts.id"), nullable=True)

    network = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)

    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")
    post = relationship("SocialPost", back_populates="logs")
