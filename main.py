# ============================================================
# 🚀 MAIN BACKEND LGD 2025 — VERSION STABLE + EMAIL CAMPAIGNS IA
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from database import Base, engine

# ✅ IMPORTANT: import the model modules BEFORE create_all()
from models.coach_profile_model import CoachProfile  # noqa: F401


# ROUTES
from routes.auth import router as auth_router
from routes.automations import router as automations_router
from routes.carrousel import router as carrousel_router
from routes.ai_text_routes import router as ai_text_router
from routes.ai_carrousel import router as ai_carrousel_router
from routes.social_posts import router as social_posts_router
from routes.social_logs import router as social_logs_router
from routes.guides import router as guides_router
from routes.library import router as library_router
from routes.campaigns import router as campaigns_router
from routes.email_campaigns import router as email_campaigns_router
from routes.content_history import router as content_history_router
from routes.statut_ia import router as ia_status_router
from routes import planner
from routes.carrousel_slides import router as carrousel_slides_router
from routes import library as library_routes
from routes.planner_schedule import router as planner_schedule_router
from routes.planner_publish import router as planner_publish_router
from routes.social_accounts import router as social_accounts_router
from routes.social_auth import router as social_auth_router
from routes.ai_quota import router as ai_quota_router
from routes.coach_ia import router as coach_ia_router
from routes.coach_profile import router as coach_profile_router
from routes.admin_ia_quotas import router as admin_ia_quotas_router
from routes.systemeio_webhook import router as systemeio_webhook_router
from routes.social_connections import router as social_connections_router
from routes.jobs_publish_due import router as jobs_publish_due_router
from routes.email_systeme_io import router as systeme_router
from routes.systeme_sync import router as systeme_sync_router
from routes.systeme_webhooks import router as systeme_webhooks_router
from routes.email_analytics_dashboard import router as email_analytics_router


app = FastAPI(title="Le Générateur Digital — Backend LGD 2026")

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://le-generateur-digital.vercel.app",
]

settings_origins = settings.CORS_ORIGINS or []
allow_origins = list(dict.fromkeys([*default_origins, *settings_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {"status": "LGD Backend Running", "version": settings.APP_VERSION}


app.include_router(auth_router)
app.include_router(automations_router)
app.include_router(carrousel_router)
app.include_router(ai_text_router)
app.include_router(ai_carrousel_router)
app.include_router(social_posts_router)
app.include_router(social_logs_router)
app.include_router(guides_router)
app.include_router(library_router)
app.include_router(campaigns_router)
app.include_router(email_campaigns_router)
app.include_router(content_history_router)
app.include_router(ia_status_router)
app.include_router(planner.router)
app.include_router(carrousel_slides_router)
app.include_router(library_routes.router)
app.include_router(planner_schedule_router)
app.include_router(planner_publish_router)
app.include_router(social_accounts_router)
app.include_router(social_auth_router)
app.include_router(social_connections_router)
app.include_router(ai_quota_router)
app.include_router(coach_profile_router)
app.include_router(coach_ia_router)
app.include_router(admin_ia_quotas_router)
app.include_router(systemeio_webhook_router)
app.include_router(jobs_publish_due_router)
app.include_router(systeme_router)
app.include_router(systeme_sync_router)
app.include_router(systeme_webhooks_router)
app.include_router(email_analytics_router)


@app.get("/health")
def health():
    return {"status": "ok"}


print("\n========== ROUTES CHARGEES ==========")
print("CORS_ORIGINS effectifs :", allow_origins)
for r in app.routes:
    try:
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        print(f"{methods:15s} {getattr(r, 'path', '')}")
    except Exception:
        pass
print("=====================================\n")
