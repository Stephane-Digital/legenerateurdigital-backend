# ============================================================
#  LGD — Settings / Environment Loader (Pydantic v2)
# ============================================================

from __future__ import annotations

import json
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --------------------------------------------------------
    # ⚙ CONFIG
    # --------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --------------------------------------------------------
    # 🧩 APP
    # --------------------------------------------------------
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"

    # --------------------------------------------------------
    # 🗄 DATABASE
    # --------------------------------------------------------
    DATABASE_URL: str

    # --------------------------------------------------------
    # 🔐 SECURITY — JWT
    # --------------------------------------------------------
    JWT_SECRET: str = Field(..., alias="SECRET_KEY")
    JWT_ALGORITHM: str = Field("HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(..., alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # --------------------------------------------------------
    # 🌐 CORS
    # --------------------------------------------------------
    CORS_ORIGINS: List[str] = Field(default_factory=list)

    # --------------------------------------------------------
    # 🔗 URLs
    # --------------------------------------------------------
    BACKEND_URL: str
    FRONTEND_URL: str

    # --------------------------------------------------------
    # 🔐 OAuth State (HMAC)
    # --------------------------------------------------------
    OAUTH_STATE_SECRET: Optional[str] = None

    # --------------------------------------------------------
    # 🛠 ADMIN
    # --------------------------------------------------------
    ADMIN_API_KEY: str
    ADMIN_EMAILS: Optional[str] = None

    # --------------------------------------------------------
    # 🤖 OPENAI (optional in local)
    # --------------------------------------------------------
    OPENAI_API_KEY: str = ""

    # --------------------------------------------------------
    # 🔥 SUPABASE (optional in local)
    # --------------------------------------------------------
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "lgd-carousels"

    # --------------------------------------------------------
    # 📲 INSTAGRAM (compat)
    # --------------------------------------------------------
    INSTAGRAM_CLIENT_ID: Optional[str] = None
    INSTAGRAM_CLIENT_SECRET: Optional[str] = None
    INSTAGRAM_REDIRECT_URI: Optional[str] = None

    # --------------------------------------------------------
    # 📘 FACEBOOK (compat)
    # --------------------------------------------------------
    FACEBOOK_CLIENT_ID: Optional[str] = None
    FACEBOOK_CLIENT_SECRET: Optional[str] = None
    FACEBOOK_REDIRECT_URI: Optional[str] = None

    # --------------------------------------------------------
    # 🧷 META (recommended)
    # --------------------------------------------------------
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None

    # --------------------------------------------------------
    # 📌 PINTEREST
    # --------------------------------------------------------
    PINTEREST_APP_ID: Optional[str] = None
    PINTEREST_APP_SECRET: Optional[str] = None

    # --------------------------------------------------------
    # 💳 SYSTEME.IO — WEBHOOK & PRICEPLAN MAPPING
    # --------------------------------------------------------
    SYSTEMEIO_WEBHOOK_SECRET: str = ""
    SYSTEMEIO_PRICEPLAN_ESSENTIEL_IDS: str = ""
    SYSTEMEIO_PRICEPLAN_PRO_IDS: str = ""
    SYSTEMEIO_PRICEPLAN_ULTIME_IDS: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None or value == "":
            return []

        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]

        if isinstance(value, str):
            raw = value.strip()

            if not raw:
                return []

            # Support JSON array string
            if raw.startswith("["):
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]

            # Support comma-separated string
            return [item.strip() for item in raw.split(",") if item.strip()]

        return value


settings = Settings()
