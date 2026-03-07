from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base


class Carrousel(Base):
    __tablename__ = "carrousel"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(String, default="")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # === RELATION AVEC SLIDES ===
    slides = relationship(
        "CarrouselSlide",
        back_populates="carrousel",
        cascade="all, delete-orphan",
        order_by="CarrouselSlide.position",
    )

    # === RELATION AVEC USER ===
    user = relationship("User", back_populates="carrousels")
