# services/campaign_service.py

from sqlalchemy.orm import Session
from models.campaign_model import Campaign
from schemas.campaign_schema import CampaignCreate, CampaignUpdate


# ---------------------------------------------------------
# Obtenir toutes les campagnes d'un utilisateur
# ---------------------------------------------------------
def get_user_campaigns(db: Session, user_id: int):
    return (
        db.query(Campaign)
        .filter(Campaign.user_id == user_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )


# ---------------------------------------------------------
# Obtenir une seule campagne
# ---------------------------------------------------------
def get_campaign(db: Session, campaign_id: int, user_id: int):
    return (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == user_id)
        .first()
    )


# ---------------------------------------------------------
# Créer une campagne
# ---------------------------------------------------------
def create_campaign(db: Session, user_id: int, data: CampaignCreate):
    new_campaign = Campaign(
        titre=data.titre,
        type=data.type,
        objectif=data.objectif,
        user_id=user_id,
    )

    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)

    return new_campaign


# ---------------------------------------------------------
# Mettre à jour une campagne
# ---------------------------------------------------------
def update_campaign(db: Session, campaign: Campaign, data: CampaignUpdate):
    campaign.titre = data.titre
    campaign.type = data.type
    campaign.objectif = data.objectif

    db.commit()
    db.refresh(campaign)

    return campaign


# ---------------------------------------------------------
# Supprimer une campagne
# ---------------------------------------------------------
def delete_campaign(db: Session, campaign: Campaign):
    db.delete(campaign)
    db.commit()
