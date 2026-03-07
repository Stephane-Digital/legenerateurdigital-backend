from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database import Base


class IAQuota(Base):
    """Quota IA par utilisateur + feature.

    IMPORTANT:
    - La table `ia_quota` (PostgreSQL) dans LGD existe déjà.
    - On s'aligne sur le schéma existant observé en prod locale:
        id, user_id, feature (NOT NULL), plan, tokens_used, credits, reset_at, created_at, updated_at
    - On NE reference PAS de colonnes inexistantes (ex: limit_tokens) pour éviter les 500.
    """

    __tablename__ = "ia_quota"
    __table_args__ = (
        UniqueConstraint("user_id", "feature", name="uq_ia_quota_user_feature"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # feature: ex "coach", "carrousel", "editor"
    feature = Column(String, nullable=False, index=True)

    # plan stocké en DB (ex: "essentiel", "pro", "ultime") ou NULL si non défini
    plan = Column(String, nullable=True, index=True)

    # tokens consommés (ou unité d'usage) pour la feature
    tokens_used = Column(Integer, nullable=False, default=0)

    # credits = limite (en tokens/units) pour la feature (choix historique LGD)
    credits = Column(Integer, nullable=False, default=0)

    # date de reset (optionnelle)
    reset_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="ia_quotas")
