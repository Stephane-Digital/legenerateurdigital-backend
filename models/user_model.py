from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Colonnes réellement présentes dans la base
    name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    # Source de vérité pour l'auth
    hashed_password = Column(String(255), nullable=True)

    # Colonne legacy encore présente dans la DB
    password = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)

    plan = Column(String(50), nullable=True, default="essentiel")
    ai_usage_limit = Column(Float, nullable=True, default=0)
    ai_last_reset = Column(DateTime, nullable=True)
    ai_usage_weekly = Column(Float, nullable=True, default=0)

    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    # ============================================================
    # RELATIONS OFFICIELLES LGD — version stable
    # ============================================================

    carrousels = relationship("Carrousel", back_populates="user", cascade="all, delete")
    automations = relationship("Automation", back_populates="user")
    social_posts = relationship("SocialPost", back_populates="user")
    logs = relationship("SocialPostLog", back_populates="user")
    library_items = relationship("LibraryItem", back_populates="user")
    guides = relationship("Guide", back_populates="user")
    campaigns = relationship("Campaign", back_populates="user")
    email_campaigns = relationship("EmailCampaign", back_populates="user", cascade="all, delete-orphan")
    histories = relationship("ContentHistory", back_populates="user")
    ia_quotas = relationship("IAQuota", back_populates="user", cascade="all, delete-orphan")
    sales_pages = relationship("SalesPage", back_populates="user", cascade="all, delete-orphan")
