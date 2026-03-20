from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)

    # ============================================================
    # RELATIONS OFFICIELLES LGD — version safe Render
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
