# ============================================================
# 🚀 MAIN BACKEND LGD 2025 — VERSION STABLE + EMAIL CAMPAIGNS IA
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from config.settings import settings
from database import Base, engine

# ✅ IMPORTANT: import the model modules BEFORE create_all()
from models.coach_profile_model import CoachProfile  # noqa: F401
from models.email_campaign_model import EmailCampaign  # noqa: F401
from models.lead_engine_memory_model import LeadEngineMemory  # noqa: F401

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
from routes.lead_engine_ai import router as lead_engine_ai_router
from routes import planner_make
from routes.ai_caption import router as ai_caption_router

app = FastAPI(title="Le Générateur Digital — Backend LGD 2026")

from fastapi.responses import JSONResponse

@app.middleware("http")
async def force_cors_on_error(request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        response = JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

    response.headers["Access-Control-Allow-Origin"] = "https://legenerateurdigital-front.vercel.app"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"

    return response

def normalize_origins(value):
    if not value:
        return []

    if isinstance(value, list):
        return [str(v).strip().rstrip("/") for v in value if str(v).strip()]

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []

        # support "a,b,c"
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]

        parts = [p.strip().strip('"').strip("'").rstrip("/") for p in raw.split(",")]
        return [p for p in parts if p]

    return []


default_origins = [
    # Local
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",

    # Prod / custom / Vercel
    "https://legenerateurdigital-front.vercel.app",
    "https://le-generateur-digital.vercel.app",
    "https://legenerateurdigital.com",
    "https://www.legenerateurdigital.com",

    # URLs Vercel déjà vues
    "https://legenerateurdigital-front-git-main-stephanes-projects-4f681f66.vercel.app",
    "https://legenerateurdigital-front-fx7bfjv8g-stephanes-projects-4f681f66.vercel.app",
]

settings_origins = normalize_origins(getattr(settings, "CORS_ORIGINS", []))
allow_origins = list(dict.fromkeys([*default_origins, *settings_origins]))

print("========== CORS LGD ==========")
print("settings.CORS_ORIGINS brut :", getattr(settings, "CORS_ORIGINS", None))
print("settings.CORS_ORIGINS norm :", settings_origins)
print("allow_origins effectifs    :", allow_origins)
print("================================")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://legenerateurdigital-front.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return Response(status_code=200)


Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {"status": "LGD Backend Running", "version": settings.APP_VERSION}


@app.get("/health")
def health():
    return {"status": "ok"}


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
app.include_router(lead_engine_ai_router)
app.include_router(planner_make.router)
app.include_router(ai_caption_router)


print("========== ROUTES CHARGEES ==========")
for r in app.routes:
    try:
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        print(f"{methods:15s} {getattr(r, 'path', '')}")
    except Exception:
        pass
print("=====================================")
