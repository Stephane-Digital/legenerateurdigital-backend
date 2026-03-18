# C:\LGD\legenerateurdigital_backend\models\sales_page_model.py

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class SalesPage(Base):
    __tablename__ = "sales_pages"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True)
    generated_content = Column(Text, nullable=True)  # JSON text (nouveau format)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation vers User
    user = relationship("User", back_populates="sales_pages")
