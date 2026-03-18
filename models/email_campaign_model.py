from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    campaign_type = Column(String(50), nullable=False, default="vente")
    duration_days = Column(Integer, nullable=False, default=7)
    sender_name = Column(String(255), nullable=False, default="Le Générateur Digital")

    offer_name = Column(String(255), nullable=True)
    target_audience = Column(Text, nullable=True)
    main_promise = Column(Text, nullable=True)
    main_objective = Column(Text, nullable=True)
    primary_cta = Column(Text, nullable=True)

    tone = Column(String(50), nullable=False, default="premium")
    sales_intensity = Column(String(50), nullable=False, default="modere")

    include_nurture = Column(Boolean, nullable=False, default=True)
    include_sales = Column(Boolean, nullable=False, default=True)
    include_objection = Column(Boolean, nullable=False, default=True)
    include_relaunch = Column(Boolean, nullable=False, default=True)

    auto_cta = Column(Boolean, nullable=False, default=True)
    optimize_subjects = Column(Boolean, nullable=False, default=True)
    progressive_pressure = Column(Boolean, nullable=False, default=True)

    generated_sequence = Column(Text, nullable=True)

    delivery_platform = Column(String(50), nullable=False, default="none")
    delivery_status = Column(String(50), nullable=False, default="draft")
    systeme_tag = Column(String(255), nullable=True)
    systeme_campaign_name = Column(String(255), nullable=True)
    delivery_payload = Column(Text, nullable=True)
    last_delivery_at = Column(DateTime, nullable=True)

    status = Column(String(50), nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="email_campaigns")
