# ============================================================
# 🚀 MAIN BACKEND LGD 2025 — VERSION STABLE (FIX Social Facebook)
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from database import Base, engine

# ✅ IMPORTANT: import the model modules BEFORE create_all()
# This ensures new tables (ex: coach_profiles) are registered in Base.metadata.
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
from routes.content_history import router as content_history_router
from routes.statut_ia import router as ia_status_router
from routes import planner
from routes.carrousel_slides import router as carrousel_slides_router
from routes import library as library_routes
from routes.planner_schedule import router as planner_schedule_router
from routes.social_accounts import router as social_accounts_router
from routes.social_auth import router as social_auth_router


# ✅ AI-Quota (Coach header)
from routes.ai_quota import router as ai_quota_router

# ✅ Coach V2 + profile persistence (NO routes/cs)
from routes.coach_ia import router as coach_ia_router
from routes.coach_profile import router as coach_profile_router
from routes.admin_ia_quotas import router as admin_ia_quotas_router
from routes.systemeio_webhook import router as systemeio_webhook_router

# ✅ Social Facebook (Meta OAuth)
from routes.social_connections import router as social_connections_router

# ✅ Jobs
from routes.jobs_publish_due import router as jobs_publish_due_router

# ============================================================
# INIT APP
# ============================================================

app = FastAPI(title="Le Générateur Digital — Backend LGD 2026")

# ============================================================
# CORS — Centralized
# ============================================================

allow_origins = settings.CORS_ORIGINS or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# DATABASE INIT
# ============================================================

Base.metadata.create_all(bind=engine)

# ============================================================
# HEALTHCHECK
# ============================================================

@app.get("/")
def home():
    return {"status": "LGD Backend Running", "version": settings.APP_VERSION}

# ============================================================
# ROUTES
# ============================================================

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
app.include_router(content_history_router)
app.include_router(ia_status_router)
app.include_router(planner.router)
app.include_router(carrousel_slides_router)
app.include_router(library_routes.router)
app.include_router(planner_schedule_router)
app.include_router(social_accounts_router)
app.include_router(social_auth_router)
app.include_router(social_connections_router)

# ✅ expose /ai-quota (used by Coach)
app.include_router(ai_quota_router)

# ✅ Coach profile persistence
app.include_router(coach_profile_router)

# ✅ Coach chat
app.include_router(coach_ia_router)

# ✅ Admin quotas + Systeme.io webhook
app.include_router(admin_ia_quotas_router)
app.include_router(systemeio_webhook_router)

# ✅ Facebook OAuth routes (router already has prefix="/social/facebook")


# ✅ Jobs
app.include_router(jobs_publish_due_router)

# ============================================================
# DEBUG (safe) — list loaded routes in logs
# ============================================================

print("\n========== ROUTES CHARGEES ==========")
for r in app.routes:
    try:
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        print(f"{methods:15s} {getattr(r, 'path', '')}")
    except Exception:
        pass
print("=====================================\n")
