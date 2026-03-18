from sqlalchemy import Column, Integer, String
from database import Base

class IAStatus(Base):
    __tablename__ = "ia_status"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="ready")
