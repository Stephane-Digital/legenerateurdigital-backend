from __future__ import annotations

"""SQLAlchemy model for the `ia_quota` table (LGD).

IMPORTANT:
Your current local PostgreSQL schema (as observed) contains:
- ia_quota: id, user_id, credits, tokens_used

This model MUST match that schema to avoid UndefinedColumn errors.
"""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from db.session import Base


class IaQuota(Base):
    __tablename__ = "ia_quota"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # `credits` is the quota limit for the current period (tokens allowed)
    credits = Column(Integer, nullable=False, default=0)

    # how many tokens have been consumed in the current period
    tokens_used = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="ia_quota", lazy="joined")
