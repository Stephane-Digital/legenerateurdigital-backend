from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    reseau = Column(String(50), nullable=False)
    statut = Column(String(50), default="scheduled", nullable=False)

    contenu = Column(Text, nullable=False)

    date_programmee = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # ✅ Publication réelle Planner
    platform_post_id = Column(String(255), nullable=True)
    publish_error = Column(Text, nullable=True)
    publish_result_raw = Column(Text, nullable=True)
    last_publish_attempt_at = Column(DateTime, nullable=True)

    supprimer_apres = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="social_posts")
    logs = relationship("SocialPostLog", back_populates="post", cascade="all, delete-orphan")
