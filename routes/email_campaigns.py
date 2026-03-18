from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config.settings import settings
from database import get_db
from models.email_campaign_model import EmailCampaign
from models.user_model import User
from schemas.email_campaign_schema import (
    EmailCampaignCreate,
    EmailCampaignGenerateRequest,
    EmailCampaignGenerateResponse,
    EmailCampaignOut,
    EmailCampaignUpdate,
    SystemeIoPrepareRequest,
    SystemeIoPrepareResponse,
)
from services.ai.email_campaign_ai import generate_email_campaign_sequence
from services.ai_quota_service import update_quota
from services.integrations.systeme_io_service import build_systeme_io_payload

router = APIRouter(prefix="/email-campaigns", tags=["Email Campaigns"])


def _extract_token(request: Request) -> Optional[str]:
    cookie_candidates = [
        request.cookies.get("lgd_token"),
        request.cookies.get("access_token"),
        request.cookies.get("token"),
    ]
    for candidate in cookie_candidates:
        if candidate:
            return candidate

    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token

    custom_header = request.headers.get("x-lgd-token") or request.headers.get("X-LGD-Token")
    if custom_header:
        return custom_header.strip()

    return None


def _resolve_current_user(request: Request, db: Session) -> User:
    token = _extract_token(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (missing cookie or bearer token)",
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token invalid or expired") from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_email_campaign_user(request: Request, db: Session = Depends(get_db)):
    return _resolve_current_user(request, db)


def _estimate_email_generation_cost(sequence: dict) -> int:
    """
    Estimation volontairement prudente pour décrémenter le quota IA existant
    sans toucher à la logique stable de ia-quotas.
    On reste sur le bucket existant `feature="coach"` car c'est celui affiché
    et piloté dans l'admin actuel.
    """
    try:
        emails = sequence.get("emails") or []
        if not isinstance(emails, list):
            emails = []

        total_chars = 0
        for email in emails:
            if not isinstance(email, dict):
                continue
            total_chars += len(str(email.get("subject") or ""))
            total_chars += len(str(email.get("preheader") or ""))
            total_chars += len(str(email.get("body") or ""))
            total_chars += len(str(email.get("cta") or ""))

        approx_tokens = max(1, total_chars // 4)

        return max(600, min(approx_tokens, 12000))
    except Exception:
        return 1200


@router.post("/generate", response_model=EmailCampaignGenerateResponse)
def generate_email_campaign(
    payload: EmailCampaignGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_email_campaign_user),
):
    sequence = generate_email_campaign_sequence(payload.model_dump())

    amount = _estimate_email_generation_cost(sequence)
    quota = update_quota(db, user.id, amount, feature="coach")
    if quota is None:
        raise HTTPException(status_code=400, detail="Quota insuffisant")

    return EmailCampaignGenerateResponse(**sequence)


@router.get("/", response_model=List[EmailCampaignOut])
def list_email_campaigns(db: Session = Depends(get_db), user=Depends(get_email_campaign_user)):
    campaigns = (
        db.query(EmailCampaign)
        .filter(EmailCampaign.user_id == user.id)
        .order_by(EmailCampaign.created_at.desc())
        .all()
    )
    return campaigns


@router.post("/", response_model=EmailCampaignOut)
def create_email_campaign(payload: EmailCampaignCreate, db: Session = Depends(get_db), user=Depends(get_email_campaign_user)):
    data = payload.model_dump()
    generated_sequence = data.get("generated_sequence")
    if isinstance(generated_sequence, (dict, list)):
        data["generated_sequence"] = json.dumps(generated_sequence, ensure_ascii=False)

    delivery_payload = data.get("delivery_payload")
    if isinstance(delivery_payload, (dict, list)):
        data["delivery_payload"] = json.dumps(delivery_payload, ensure_ascii=False)

    campaign = EmailCampaign(user_id=user.id, **data)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=EmailCampaignOut)
def get_email_campaign(campaign_id: int, db: Session = Depends(get_db), user=Depends(get_email_campaign_user)):
    campaign = (
        db.query(EmailCampaign)
        .filter(EmailCampaign.id == campaign_id, EmailCampaign.user_id == user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne emailing introuvable")
    return campaign


@router.put("/{campaign_id}", response_model=EmailCampaignOut)
def update_email_campaign(campaign_id: int, payload: EmailCampaignUpdate, db: Session = Depends(get_db), user=Depends(get_email_campaign_user)):
    campaign = (
        db.query(EmailCampaign)
        .filter(EmailCampaign.id == campaign_id, EmailCampaign.user_id == user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne emailing introuvable")

    update_data = payload.model_dump(exclude_unset=True)
    if isinstance(update_data.get("generated_sequence"), (dict, list)):
        update_data["generated_sequence"] = json.dumps(update_data["generated_sequence"], ensure_ascii=False)
    if isinstance(update_data.get("delivery_payload"), (dict, list)):
        update_data["delivery_payload"] = json.dumps(update_data["delivery_payload"], ensure_ascii=False)

    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}")
def delete_email_campaign(campaign_id: int, db: Session = Depends(get_db), user=Depends(get_email_campaign_user)):
    campaign = (
        db.query(EmailCampaign)
        .filter(EmailCampaign.id == campaign_id, EmailCampaign.user_id == user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne emailing introuvable")

    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


@router.post("/{campaign_id}/prepare-systeme-io", response_model=SystemeIoPrepareResponse)
def prepare_systeme_io_campaign(
    campaign_id: int,
    payload: SystemeIoPrepareRequest,
    db: Session = Depends(get_db),
    user=Depends(get_email_campaign_user),
):
    campaign = (
        db.query(EmailCampaign)
        .filter(EmailCampaign.id == campaign_id, EmailCampaign.user_id == user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne emailing introuvable")

    if not campaign.generated_sequence:
        raise HTTPException(status_code=400, detail="Aucune séquence générée à préparer pour Systeme.io")

    try:
        sequence = json.loads(campaign.generated_sequence)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Séquence générée invalide") from exc

    systeme_tag = payload.systeme_tag or campaign.systeme_tag
    systeme_campaign_name = payload.systeme_campaign_name or campaign.systeme_campaign_name or campaign.name

    prepared_payload = build_systeme_io_payload(
        campaign=campaign,
        sequence=sequence,
        systeme_tag=systeme_tag,
        systeme_campaign_name=systeme_campaign_name,
        mode=payload.mode,
    )

    campaign.delivery_platform = "systeme_io"
    campaign.delivery_status = "ready" if payload.mode in {"ready", "payload"} else "draft"
    campaign.systeme_tag = systeme_tag
    campaign.systeme_campaign_name = systeme_campaign_name
    campaign.delivery_payload = json.dumps(prepared_payload, ensure_ascii=False)
    campaign.last_delivery_at = datetime.utcnow()
    campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    return SystemeIoPrepareResponse(
        campaign_id=campaign.id,
        delivery_platform=campaign.delivery_platform,
        delivery_status=campaign.delivery_status,
        payload=prepared_payload,
    )
