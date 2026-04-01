from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from database import Base


class LeadEngineMemory(Base):
    __tablename__ = "lead_engine_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    memory_type = Column(String(80), nullable=False, default="brief")
    content = Column(Text, nullable=False)

    emotional_profile = Column(Text, nullable=True)
    business_context = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
