
from fastapi import APIRouter
from services.integrations.systeme_sync_service import (
    fetch_systeme_contacts,
    fetch_systeme_tags,
    fetch_systeme_campaigns,
)

router = APIRouter(prefix="/systeme-sync")


@router.get("/contacts")
def sync_contacts():
    return fetch_systeme_contacts()


@router.get("/tags")
def sync_tags():
    return fetch_systeme_tags()


@router.get("/campaigns")
def sync_campaigns():
    return fetch_systeme_campaigns()
