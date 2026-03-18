
from fastapi import APIRouter
from services.analytics.email_dashboard_service import get_dashboard_stats

router = APIRouter(prefix="/email-analytics")

@router.get("/dashboard")
def email_dashboard():
    """
    Endpoint pour le dashboard Emailing IA LGD
    """
    return get_dashboard_stats()
