from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

try:
    from database import Base  # type: ignore
except Exception:
    from db import Base  # type: ignore


class CoachProfile(Base):
    """User memory for Coach Alex V2.

    Stores stable user context + preferences to improve missions and pedagogy.
    JSON-ish data is stored as TEXT for simplicity and maximum compatibility.
    """

    __tablename__ = "coach_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    profile_json = Column(Text, nullable=False, default="{}")

    intent = Column(String(50), nullable=True)
    level = Column(String(50), nullable=True)
    time_per_day = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", name="uq_coach_profiles_user_id"),)
