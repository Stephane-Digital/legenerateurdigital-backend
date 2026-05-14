from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy.orm import Session

from services.user_entitlements import clear_plan_override, get_effective_plan, set_base_plan

try:
    from models.ia_quota_model import IAQuota as QuotaModel  # type: ignore
except Exception:
    try:
        from models.ia_quota_model import IaQuota as QuotaModel  # type: ignore
    except Exception:
        QuotaModel = None  # type: ignore


# ======================================================
# LGD — SOURCE DE VÉRITÉ QUOTAS = ia_quota
#
# Trial = 150 000 total (20 000 / jour sur 7 jours)
# Essentiel = 2 000 000
# Pro = 6 000 000
# Ultime = 15 000 000
#
# Correctif coût IA 2026-05 :
# - Tous les appels IA consomment le bucket canonique "global".
# - Le plafond journalier est réellement bloquant SANS migration DB.
# - Le suivi journalier utilise une ligne technique ia_quota par jour :
#   feature="global_daily:YYYY-MM-DD".
# - Le frontend continue de lire /ai-quota/global comme avant.
# ======================================================

_CANONICAL_FEATURE = "global"
_DAILY_FEATURE_PREFIX = "global_daily:"
_LEGACY_FEATURES_TO_SYNC = ("coach",)


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def _default_limit_for_plan(plan: str) -> int:
    p = (plan or "").lower()
    if "cancel" in p or "inactive" in p or "stopped" in p:
        return 0
    if "trial" in p or "azur" in p or "starter" in p or "decouverte" in p or "découverte" in p:
        return 150_000
    if "ult" in p:
        return 15_000_000
    if "pro" in p:
        return 6_000_000
    return 2_000_000


def _daily_limit_for_plan(plan: str, monthly_limit: int) -> int:
    p = (plan or "").lower()
    if "cancel" in p or "inactive" in p or "stopped" in p or int(monthly_limit or 0) <= 0:
        return 0
    if "trial" in p or "azur" in p or "starter" in p or "decouverte" in p or "découverte" in p:
        return 20_000
    if "ult" in p or int(monthly_limit or 0) == 15_000_000:
        return 500_000
    if "pro" in p or int(monthly_limit or 0) == 6_000_000:
        return 250_000
    return 80_000


def _today_key() -> str:
    return datetime.date.today().isoformat()


def _daily_feature() -> str:
    return f"{_DAILY_FEATURE_PREFIX}{_today_key()}"


def _get_used(quota: Any) -> int:
    if hasattr(quota, "tokens_used"):
        return _to_int(getattr(quota, "tokens_used", 0), 0)
    if hasattr(quota, "used_tokens"):
        return _to_int(getattr(quota, "used_tokens", 0), 0)
    return 0


def _set_used(quota: Any, value: int) -> None:
    v = max(0, int(value))
    if hasattr(quota, "tokens_used"):
        setattr(quota, "tokens_used", v)
        return
    if hasattr(quota, "used_tokens"):
        setattr(quota, "used_tokens", v)
        return


def _get_limit(quota: Any) -> int:
    if hasattr(quota, "credits") and getattr(quota, "credits", None) is not None:
        return _to_int(getattr(quota, "credits", 0), 0)
    if hasattr(quota, "tokens_limit") and getattr(quota, "tokens_limit", None) is not None:
        return _to_int(getattr(quota, "tokens_limit", 0), 0)
    if hasattr(quota, "limit_tokens") and getattr(quota, "limit_tokens", None) is not None:
        return _to_int(getattr(quota, "limit_tokens", 0), 0)
    return 0


def _set_limit(quota: Any, value: int) -> None:
    v = max(0, int(value))
    if hasattr(quota, "credits"):
        setattr(quota, "credits", v)
        return
    if hasattr(quota, "tokens_limit"):
        setattr(quota, "tokens_limit", v)
        return
    if hasattr(quota, "limit_tokens"):
        setattr(quota, "limit_tokens", v)
        return


def _set_remaining(quota: Any, remaining: int) -> None:
    if hasattr(quota, "remaining"):
        try:
            setattr(quota, "remaining", max(0, int(remaining)))
        except Exception:
            pass


def _set_plan(quota: Any, plan: str) -> None:
    if hasattr(quota, "plan"):
        try:
            setattr(quota, "plan", str(plan or "essentiel").lower())
        except Exception:
            pass


def _get_plan(quota: Any) -> str:
    return str(getattr(quota, "plan", None) or "essentiel").lower()


def _set_reset_at(quota: Any, value: datetime.datetime | None) -> None:
    if hasattr(quota, "reset_at"):
        try:
            setattr(quota, "reset_at", value)
        except Exception:
            pass


def _next_midnight_utc() -> datetime.datetime:
    now = datetime.datetime.now(datetime.timezone.utc)
    tomorrow = now.date() + datetime.timedelta(days=1)
    return datetime.datetime.combine(tomorrow, datetime.time.min, tzinfo=datetime.timezone.utc)


def _query_quota(db: Session, user_id: int, feature: str):
    if QuotaModel is None:
        raise RuntimeError("QuotaModel introuvable (models.ia_quota_model)")

    query = db.query(QuotaModel).filter(QuotaModel.user_id == int(user_id))  # type: ignore
    if hasattr(QuotaModel, "feature"):
        query = query.filter(QuotaModel.feature == feature)  # type: ignore
    return query.first()


def _create_quota(db: Session, user_id: int, feature: str, *, plan: str, limit: int, used: int = 0):
    if QuotaModel is None:
        raise RuntimeError("QuotaModel introuvable (models.ia_quota_model)")

    quota = QuotaModel()  # type: ignore
    setattr(quota, "user_id", int(user_id))
    if hasattr(quota, "feature"):
        setattr(quota, "feature", feature)
    _set_plan(quota, plan)
    _set_limit(quota, limit)
    _set_used(quota, used)
    _set_remaining(quota, max(limit - used, 0))
    if feature.startswith(_DAILY_FEATURE_PREFIX):
        _set_reset_at(quota, _next_midnight_utc())
    db.add(quota)
    db.flush()
    db.refresh(quota)
    return quota


def get_or_create_quota(db: Session, user_id: int, feature: str = _CANONICAL_FEATURE):
    """Retourne le quota demandé, en gardant `global` comme source d'affichage.

    Les anciennes features restent lisibles pour compatibilité, mais toute consommation
    réelle passe par update_quota(), qui force le bucket global + daily.
    """
    if QuotaModel is None:
        raise RuntimeError("QuotaModel introuvable (models.ia_quota_model)")

    feature = (feature or _CANONICAL_FEATURE).strip() or _CANONICAL_FEATURE
    quota = _query_quota(db, int(user_id), feature)

    if quota:
        limit = _get_limit(quota)
        if not feature.startswith(_DAILY_FEATURE_PREFIX):
            plan = _get_plan(quota)
            plan_limit = _default_limit_for_plan(plan)
            if limit <= 0 or limit < plan_limit:
                _set_limit(quota, plan_limit)
                _set_remaining(quota, max(_get_limit(quota) - _get_used(quota), 0))
                db.add(quota)
                db.flush()
                db.refresh(quota)
        return quota

    # Si on crée une feature non-global, on récupère le plan du global si possible.
    plan = "essentiel"
    global_quota = None
    if feature != _CANONICAL_FEATURE:
        global_quota = _query_quota(db, int(user_id), _CANONICAL_FEATURE)
        if global_quota:
            plan = _get_plan(global_quota)

    if feature.startswith(_DAILY_FEATURE_PREFIX):
        monthly_limit = _get_limit(global_quota) if global_quota else _default_limit_for_plan(plan)
        limit = _daily_limit_for_plan(plan, monthly_limit)
    else:
        limit = _default_limit_for_plan(plan)

    return _create_quota(db, int(user_id), feature, plan=plan, limit=limit, used=0)


def _get_global_quota(db: Session, user_id: int):
    quota = get_or_create_quota(db, int(user_id), _CANONICAL_FEATURE)
    limit = _get_limit(quota)
    if limit <= 0:
        _set_limit(quota, _default_limit_for_plan(_get_plan(quota)))
        _set_remaining(quota, max(_get_limit(quota) - _get_used(quota), 0))
        db.add(quota)
        db.flush()
        db.refresh(quota)
    return quota


def _get_daily_quota(db: Session, user_id: int, *, plan: str, monthly_limit: int):
    feature = _daily_feature()
    daily_limit = _daily_limit_for_plan(plan, monthly_limit)
    quota = _query_quota(db, int(user_id), feature)
    if quota is None:
        quota = _create_quota(db, int(user_id), feature, plan=plan, limit=daily_limit, used=0)
    else:
        _set_plan(quota, plan)
        _set_limit(quota, daily_limit)
        _set_remaining(quota, max(daily_limit - _get_used(quota), 0))
        _set_reset_at(quota, _next_midnight_utc())
        db.add(quota)
        db.flush()
        db.refresh(quota)
    return quota


def sync_plan_quotas(db: Session, user_id: int, plan: str) -> None:
    """Synchronise le plan réel reçu depuis Systeme.io / auth.

    - le plan de base est stocké dans user_plan_state ;
    - un bonus actif reste respecté ;
    - canceled annule le bonus et bloque réellement l'IA.
    """
    clean_base_plan = str(plan or "essentiel").lower()

    if "cancel" in clean_base_plan or "inactive" in clean_base_plan or "stopped" in clean_base_plan:
        clean_base_plan = "canceled"
        try:
            clear_plan_override(db, user_id=int(user_id))
        except Exception:
            pass

    set_base_plan(db, user_id=int(user_id), base_plan=clean_base_plan, source="sync_plan_quotas")

    effective_plan, _override = get_effective_plan(db, user_id=int(user_id), base_plan=clean_base_plan)
    clean_plan = str(effective_plan or clean_base_plan or "essentiel").lower()
    limit_tokens = _default_limit_for_plan(clean_plan)

    global_quota = get_or_create_quota(db, int(user_id), feature=_CANONICAL_FEATURE)
    _set_plan(global_quota, clean_plan)
    _set_used(global_quota, 0)
    _set_limit(global_quota, limit_tokens)
    _set_remaining(global_quota, limit_tokens)
    db.add(global_quota)

    for feature_name in _LEGACY_FEATURES_TO_SYNC:
        quota = get_or_create_quota(db, int(user_id), feature=feature_name)
        _set_plan(quota, clean_plan)
        _set_used(quota, 0)
        _set_limit(quota, limit_tokens)
        _set_remaining(quota, limit_tokens)
        db.add(quota)

    daily_quota = _get_daily_quota(db, int(user_id), plan=clean_plan, monthly_limit=limit_tokens)
    _set_used(daily_quota, 0)
    _set_remaining(daily_quota, _daily_limit_for_plan(clean_plan, limit_tokens))
    db.add(daily_quota)

    db.flush()


def update_quota(db: Session, user_id: int, amount: int, feature: str = _CANONICAL_FEATURE):
    """Décrémente réellement le quota IA.

    Important : `feature` est conservé dans la signature pour compatibilité,
    mais la consommation est volontairement centralisée sur `global` pour éviter
    les contournements coach/lead/emailing.
    """
    amt = _to_int(amount, 0)
    if amt <= 0:
        amt = 1

    global_quota = _get_global_quota(db, int(user_id))

    try:
        effective_plan, _override = get_effective_plan(db, user_id=int(user_id), base_plan=_get_plan(global_quota))
        effective_limit = _default_limit_for_plan(effective_plan)
        if _get_plan(global_quota) != effective_plan or _get_limit(global_quota) != effective_limit:
            _set_plan(global_quota, effective_plan)
            _set_limit(global_quota, effective_limit)
            _set_remaining(global_quota, max(effective_limit - _get_used(global_quota), 0))
            db.add(global_quota)
            db.flush()
            db.refresh(global_quota)
    except Exception:
        pass

    plan = _get_plan(global_quota)
    monthly_limit = _get_limit(global_quota)
    monthly_used = _get_used(global_quota)

    daily_quota = _get_daily_quota(db, int(user_id), plan=plan, monthly_limit=monthly_limit)
    daily_limit = _get_limit(daily_quota)
    daily_used = _get_used(daily_quota)

    if monthly_limit <= 0 or daily_limit <= 0:
        return None

    if daily_used + amt > daily_limit:
        return None

    if monthly_used + amt > monthly_limit:
        return None

    _set_used(global_quota, monthly_used + amt)
    _set_remaining(global_quota, max(monthly_limit - _get_used(global_quota), 0))
    db.add(global_quota)

    _set_used(daily_quota, daily_used + amt)
    _set_remaining(daily_quota, max(daily_limit - _get_used(daily_quota), 0))
    _set_reset_at(daily_quota, _next_midnight_utc())
    db.add(daily_quota)

    db.commit()
    db.refresh(global_quota)
    return global_quota
