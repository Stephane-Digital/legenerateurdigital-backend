"""
LGD - models package bootstrap

But:
- Eviter tout crash au démarrage (ModuleNotFoundError) à cause d'un import de modèle inexistant.
- Importer (best-effort) les modules de modèles présents afin d'enregistrer les mappers SQLAlchemy.
- Exporter les classes "core" si elles existent (User, SalesPage, IAQuota, etc.)

Règle:
- NE JAMAIS référencer ici des noms de fichiers inexistants.
- Utiliser des imports "safe" (try/except) pour rester robuste.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Optional

_MODEL_MODULES = [
    "user_model",
    "sales_page_model",
    "ia_quota_model",
    "guide_model",
    "library_item_model",
    "content_history_model",
    "campaign_model",
    "email_campaign_model",
    "automation_model",
    "carrousel_model",
    "carrousel_slide_model",
    "social_post",
    "social_post_log",
    "social_account",
    "ia_status",
    "statut_ia_model",
    "coach_profile_model",
]


def _safe_import(module_name: str) -> Optional[Any]:
    try:
        return import_module(f"{__name__}.{module_name}")
    except ModuleNotFoundError:
        return None
    except Exception:
        return None


for _m in _MODEL_MODULES:
    _safe_import(_m)

try:
    from .user_model import User  # noqa: F401
except Exception:
    User = None  # type: ignore

try:
    from .sales_page_model import SalesPage  # noqa: F401
except Exception:
    SalesPage = None  # type: ignore

try:
    from .ia_quota_model import IAQuota  # noqa: F401
except Exception:
    IAQuota = None  # type: ignore

try:
    from .coach_profile_model import CoachProfile  # noqa: F401
except Exception:
    CoachProfile = None  # type: ignore

try:
    from .email_campaign_model import EmailCampaign  # noqa: F401
except Exception:
    EmailCampaign = None  # type: ignore

__all__ = [
    "User",
    "SalesPage",
    "IAQuota",
    "CoachProfile",
    "EmailCampaign",
]
