from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship

from database import Base


class SocialCarrousel(Base):
    __tablename__ = "social_carrousel"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    topic = Column(String(255), nullable=True)
    source = Column(String(50), default="ia")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    slides = relationship(
        "SocialCarrouselSlide",
        back_populates="carrousel",
        cascade="all, delete-orphan",
    )


class SocialCarrouselSlide(Base):
    __tablename__ = "social_carrousel_slides"

    id = Column(Integer, primary_key=True, index=True)
    carrousel_id = Column(Integer, ForeignKey("social_carrousel.id", ondelete="CASCADE"))

    position = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)

    carrousel = relationship("SocialCarrousel", back_populates="slides")
