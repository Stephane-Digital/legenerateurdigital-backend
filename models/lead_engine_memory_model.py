from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from database import Base


class LeadEngineMemory(Base):
    __tablename__ = "lead_engine_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    memory_type = Column(String(80), nullable=False, default="brief")
    goal = Column(String(120), nullable=True)
    content = Column(Text, nullable=False)

    emotional_profile = Column(Text, nullable=True)
    business_context = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
