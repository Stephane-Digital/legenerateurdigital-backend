from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database import get_db
from services.auth_service import get_current_user
from models.campaign_model import Campaign

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


class CampaignBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "draft"


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CampaignOut(CampaignBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[CampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.user_id == user.id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return campaigns


@router.post("/", response_model=CampaignOut)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    campaign = Campaign(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.user_id == user.id,
        )
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    return campaign


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.user_id == user.id,
        )
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.user_id == user.id,
        )
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")

    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}
