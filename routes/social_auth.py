from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.social_account import SocialAccount
from routes.auth import get_current_user

from services.oauth_instagram import get_instagram_auth_url, exchange_instagram_code
from services.oauth_tiktok import get_tiktok_auth_url, exchange_tiktok_code
from services.oauth_linkedin import get_linkedin_auth_url, exchange_linkedin_code
from services.oauth_facebook import get_facebook_auth_url, exchange_facebook_code

router = APIRouter(prefix="/social-auth", tags=["OAuth Social"])

# ==========================================================
# 1. Obtenir l'URL d'autorisation pour un réseau
# ==========================================================
@router.get("/connect/{provider}")
def get_auth_url(provider: str):
    if provider == "instagram":
        return {"url": get_instagram_auth_url()}

    if provider == "tiktok":
        return {"url": get_tiktok_auth_url()}

    if provider == "linkedin":
        return {"url": get_linkedin_auth_url()}

    if provider == "facebook":
        return {"url": get_facebook_auth_url()}

    raise HTTPException(400, "Provider non supporté")


# ==========================================================
# 2. Callback OAuth (réception du code)
# ==========================================================
@router.get("/callback/{provider}")
def oauth_callback(provider: str, code: str, db: Session = Depends(get_db), user=Depends(get_current_user)):

    if provider == "instagram":
        tokens = exchange_instagram_code(code)

    elif provider == "tiktok":
        tokens = exchange_tiktok_code(code)

    elif provider == "linkedin":
        tokens = exchange_linkedin_code(code)

    elif provider == "facebook":
        tokens = exchange_facebook_code(code)

    else:
        raise HTTPException(400, "Provider non supporté")

    account = SocialAccount(
        user_id=user.id,
        provider=provider,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in")
    )

    db.add(account)
    db.commit()
    return {"status": "connected", "provider": provider}

@router.get("/user/social-accounts")
def user_accounts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return db.query(SocialAccount).filter(
        SocialAccount.user_id == user.id
    ).all()
