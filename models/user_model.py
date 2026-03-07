from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)

    # Permissions
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())

    # ============================================================
    # RELATIONS OFFICIELLES LGD — version stable
    # ============================================================

    # Carrousels
    carrousels = relationship("Carrousel", back_populates="user", cascade="all, delete")

    # Automatisations
    automations = relationship("Automation", back_populates="user")

    # Social Posts
    social_posts = relationship("SocialPost", back_populates="user")
    logs = relationship("SocialPostLog", back_populates="user")

    # Library
    library_items = relationship("LibraryItem", back_populates="user")

    # Guides
    guides = relationship("Guide", back_populates="user")

    # Campaigns
    campaigns = relationship("Campaign", back_populates="user")

    # History
    histories = relationship("ContentHistory", back_populates="user")

    # IA Quotas (Admin + Coach)
    ia_quotas = relationship("IAQuota", back_populates="user", cascade="all, delete-orphan")

    # Sales Pages (nécessaire pour le mapper SalesPage.back_populates="user")
    sales_pages = relationship("SalesPage", back_populates="user", cascade="all, delete-orphan")
