from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base


class IAStatus(Base):
    __tablename__ = "ia_status"

    id = Column(Integer, primary_key=True, index=True)

    # Exemple : "idle", "generating", "error"
    status = Column(String(50), nullable=False, default="idle")

    # Dernier message (log interne IA)
    message = Column(Text, nullable=True)

    # Quand la dernière action IA a eu lieu
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
