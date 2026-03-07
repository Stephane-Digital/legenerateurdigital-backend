from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class SlideLibraryItem(Base):
    __tablename__ = "slide_library"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    name = Column(String, nullable=False)
    category = Column(String, nullable=True)

    data = Column(JSON, nullable=False)  # src-only, same format as slides

    created_at = Column(DateTime, default=datetime.utcnow)
