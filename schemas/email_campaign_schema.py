from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

CampaignType = Literal["vente", "nurturing", "lancement", "relance"]
ToneType = Literal["premium", "direct", "storytelling", "pedagogique"]
SalesIntensityType = Literal["doux", "modere", "fort"]
EmailKind = Literal["nurture", "vente", "objection", "relance"]
DeliveryStatus = Literal["draft", "ready", "sent", "failed"]


class EmailCampaignBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    campaign_type: CampaignType = "vente"
    duration_days: Literal[7, 14, 30] = 7
    sender_name: str = Field(default="Le Générateur Digital", min_length=2, max_length=255)
    offer_name: Optional[str] = None
    target_audience: Optional[str] = None
    main_promise: Optional[str] = None
    main_objective: Optional[str] = None
    primary_cta: Optional[str] = None
    tone: ToneType = "premium"
    sales_intensity: SalesIntensityType = "modere"
    include_nurture: bool = True
    include_sales: bool = True
    include_objection: bool = True
    include_relaunch: bool = True
    auto_cta: bool = True
    optimize_subjects: bool = True
    progressive_pressure: bool = True


class EmailCampaignGenerateRequest(EmailCampaignBase):
    pass


class EmailSequenceItem(BaseModel):
    day: int
    email_type: EmailKind
    subject: str
    preheader: str
    body: str
    cta: str


class EmailCampaignGenerateResponse(BaseModel):
    campaign_name: str
    campaign_type: CampaignType
    duration_days: int
    sender_name: str = "Le Générateur Digital"
    emails: List[EmailSequenceItem]


class EmailCampaignCreate(EmailCampaignBase):
    generated_sequence: Optional[Union[str, dict, list]] = None
    delivery_platform: str = "none"
    delivery_status: DeliveryStatus = "draft"
    systeme_tag: Optional[str] = None
    systeme_campaign_name: Optional[str] = None
    delivery_payload: Optional[Union[str, dict, list]] = None
    status: str = "draft"


class EmailCampaignUpdate(BaseModel):
    name: Optional[str] = None
    campaign_type: Optional[CampaignType] = None
    duration_days: Optional[Literal[7, 14, 30]] = None
    sender_name: Optional[str] = None
    offer_name: Optional[str] = None
    target_audience: Optional[str] = None
    main_promise: Optional[str] = None
    main_objective: Optional[str] = None
    primary_cta: Optional[str] = None
    tone: Optional[ToneType] = None
    sales_intensity: Optional[SalesIntensityType] = None
    include_nurture: Optional[bool] = None
    include_sales: Optional[bool] = None
    include_objection: Optional[bool] = None
    include_relaunch: Optional[bool] = None
    auto_cta: Optional[bool] = None
    optimize_subjects: Optional[bool] = None
    progressive_pressure: Optional[bool] = None
    generated_sequence: Optional[Union[str, dict, list]] = None
    delivery_platform: Optional[str] = None
    delivery_status: Optional[DeliveryStatus] = None
    systeme_tag: Optional[str] = None
    systeme_campaign_name: Optional[str] = None
    delivery_payload: Optional[Union[str, dict, list]] = None
    status: Optional[str] = None


class EmailCampaignOut(EmailCampaignBase):
    id: int
    generated_sequence: Optional[str] = None
    delivery_platform: str
    delivery_status: str
    systeme_tag: Optional[str] = None
    systeme_campaign_name: Optional[str] = None
    delivery_payload: Optional[str] = None
    status: str
    last_delivery_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemeIoPrepareRequest(BaseModel):
    systeme_tag: Optional[str] = None
    systeme_campaign_name: Optional[str] = None
    mode: Literal["draft", "ready", "payload"] = "ready"


class SystemeIoPrepareResponse(BaseModel):
    campaign_id: int
    delivery_platform: str
    delivery_status: str
    payload: dict
