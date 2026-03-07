from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class CarrouselSlide(Base):
    __tablename__ = "carrousel_slides"

    id = Column(Integer, primary_key=True, index=True)

    carrousel_id = Column(Integer, ForeignKey("carrousel.id", ondelete="CASCADE"), nullable=False)

    position = Column(Integer, nullable=False, default=0)
    title = Column(String, default="")
    json_layers = Column(Text, default="[]")
    thumbnail_url = Column(String, nullable=True)

    # === RELATION AVEC CARROUSEL ===
    carrousel = relationship("Carrousel", back_populates="slides")
