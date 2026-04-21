from __future__ import annotations

import hmac
import hashlib
import inspect as pyinspect
import json
import os
from typing import Any, Dict, Optional, Set

import requests
from fastapi import HTTPException
from sqlalchemy import inspect as sqla_inspect, text
from sqlalchemy.orm import Session

from services.ai_quota_service import get_or_create_quota


DEFAULT_PLAN = "essentiel"
PLAN_LIMITS = {
    "essentiel": 400_000,
    "pro": 1_000_000,
    "ultime": 2_500_000,
}


def _setting(name: str, default: Any = None) -> Any:
    value = os.getenv(name, default)
    return value if value not in (None, "") else default


def _normalize_plan(plan: Any) -> str:
    p = str(plan or "").strip().lower()
    if p in {"ultimate", "ultime"}:
        return "ultime"
    if p in {"pro", "professional"}:
        return "pro"
    return DEFAULT_PLAN


def _normalize_cancel_mode(mode: Any) -> str:
    raw = str(mode or "").strip().lower()
    if raw in {"immediate", "now", "cancel_now"}:
        return "immediate"
    return "end_of_period"


def _limit_for_plan(plan: Any) -> int:
    return int(PLAN_LIMITS.get(_normalize_plan(plan), PLAN_LIMITS[DEFAULT_PLAN]))


def _ids_from_env(name: str) -> Set[int]:
    raw = str(_setting(name, "") or "").strip()
    if not raw:
        return set()

    out: Set[int] = set()
    for chunk in raw.split(','):
        part = chunk.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except Exception:
            pass
    return out


def plan_from_priceplan_id(priceplan_id: Optional[int]) -> Optional[str]:
    if priceplan_id is None:
        return None
    if int(priceplan_id) in _ids_from_env('SYSTEMEIO_PRICEPLAN_ULTIME_IDS'):
        return 'ultime'
    if int(priceplan_id) in _ids_from_env('SYSTEMEIO_PRICEPLAN_PRO_IDS'):
        return 'pro'
    if int(priceplan_id) in _ids_from_env('SYSTEMEIO_PRICEPLAN_ESSENTIEL_IDS'):
        return 'essentiel'
    return None


def compute_webhook_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(secret: str, raw_body: bytes, provided_signature: str) -> bool:
    expected = compute_webhook_signature(secret, raw_body)
    return bool(provided_signature) and hmac.compare_digest(provided_signature, expected)


def _extract_user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user['id'])
    return int(getattr(user, 'id'))


def _extract_user_email(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get('email') or '').strip().lower()
    return str(getattr(user, 'email', '') or '').strip().lower()


def _extract_user_plan(user: Any) -> str:
    if isinstance(user, dict):
        return _normalize_plan(user.get('plan'))
    return _normalize_plan(getattr(user, 'plan', None))


def _users_columns(db: Session) -> set[str]:
    try:
        engine = db.get_bind()
        return {col['name'] for col in sqla_inspect(engine).get_columns('users')}
    except Exception:
        return set()


def _set_users_plan(db: Session, user_id: int, plan: str) -> None:
    columns = _users_columns(db)
    plan_col = 'plan' if 'plan' in columns else ('subscription_plan' if 'subscription_plan' in columns else None)
    if not plan_col:
        return
    db.execute(text(f"UPDATE users SET {plan_col} = :plan WHERE id = :uid"), {'plan': plan, 'uid': int(user_id)})


def _all_quota_features_for_user(db: Session, user_id: int) -> list[str]:
    rows = db.execute(
        text("SELECT DISTINCT feature FROM ia_quota WHERE user_id = :uid"),
        {'uid': int(user_id)},
    ).fetchall()
    features = [str(r[0]).strip() for r in rows if r and r[0]]
    for fallback in ('global', 'coach'):
        if fallback not in features:
            features.append(fallback)
    return features


def sync_local_subscription_state(
    db: Session,
    *,
    user_id: int,
    plan: str,
    reset_usage: bool,
    source: str,
) -> Dict[str, Any]:
    final_plan = _normalize_plan(plan)
    tokens_limit = _limit_for_plan(final_plan)

    _set_users_plan(db, int(user_id), final_plan)

    updated_features: list[str] = []
    for feature in _all_quota_features_for_user(db, int(user_id)):
        quota = get_or_create_quota(db, int(user_id), feature=feature)

        if hasattr(quota, 'plan'):
            quota.plan = final_plan
        if hasattr(quota, 'credits'):
            quota.credits = tokens_limit
        if hasattr(quota, 'tokens_limit'):
            quota.tokens_limit = tokens_limit
        if hasattr(quota, 'limit_tokens'):
            quota.limit_tokens = tokens_limit
        if reset_usage:
            if hasattr(quota, 'tokens_used'):
                quota.tokens_used = 0
            if hasattr(quota, 'used_tokens'):
                quota.used_tokens = 0
            if hasattr(quota, 'remaining'):
                quota.remaining = tokens_limit

        db.add(quota)
        updated_features.append(feature)

    db.commit()

    return {
        'ok': True,
        'user_id': int(user_id),
        'plan': final_plan,
        'tokens_limit': tokens_limit,
        'quota_features_updated': updated_features,
        'reset_usage': bool(reset_usage),
        'source': source,
    }


def _remote_headers() -> Dict[str, str]:
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    api_key = str(_setting('SYSTEME_IO_API_KEY', '') or '').strip()
    if api_key:
        headers['X-API-Key'] = api_key
    bearer = str(_setting('SYSTEME_IO_API_BEARER', '') or '').strip()
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    return headers


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(url, json=payload, headers=_remote_headers(), timeout=30)
    content_type = (response.headers.get('content-type') or '').lower()
    body: Any
    if 'application/json' in content_type:
        try:
            body = response.json()
        except Exception:
            body = {'raw': response.text}
    else:
        body = {'raw': response.text}

    if response.status_code not in (200, 201, 202, 204):
        raise HTTPException(
            status_code=502,
            detail={
                'message': 'Annulation Systeme.io refusée',
                'status_code': response.status_code,
                'response': body,
            },
        )

    return {
        'status_code': response.status_code,
        'response': body,
    }


def cancel_subscription_remote(
    *,
    email: str,
    cancel_mode: str,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    clean_email = str(email or '').strip().lower()
    if not clean_email:
        raise HTTPException(status_code=400, detail='Email utilisateur introuvable')

    mode = _normalize_cancel_mode(cancel_mode)
    payload = {
        'email': clean_email,
        'cancel_mode': mode,
        'reason': str(reason or '').strip() or None,
        'user_id': int(user_id) if user_id is not None else None,
    }

    direct_url = str(_setting('SYSTEME_IO_CANCEL_SUBSCRIPTION_URL', '') or '').strip()
    if direct_url:
        result = _post_json(direct_url, payload)
        result['transport'] = 'direct_url'
        return result

    base_url = str(_setting('SYSTEME_IO_API_BASE_URL', '') or '').rstrip('/')
    cancel_path = str(_setting('SYSTEME_IO_CANCEL_SUBSCRIPTION_PATH', '') or '').strip()
    if base_url and cancel_path:
        final_url = f"{base_url}/{cancel_path.lstrip('/')}"
        result = _post_json(final_url, payload)
        result['transport'] = 'api_path'
        return result

    webhook_url = str(_setting('SYSTEME_IO_CANCEL_SUBSCRIPTION_WEBHOOK_URL', '') or '').strip()
    if webhook_url:
        result = _post_json(webhook_url, payload)
        result['transport'] = 'webhook_url'
        return result

    raise HTTPException(
        status_code=503,
        detail=(
            'Aucune action réelle Systeme.io configurée. '
            'Ajoute SYSTEME_IO_CANCEL_SUBSCRIPTION_URL, '
            'ou SYSTEME_IO_API_BASE_URL + SYSTEME_IO_CANCEL_SUBSCRIPTION_PATH, '
            'ou SYSTEME_IO_CANCEL_SUBSCRIPTION_WEBHOOK_URL.'
        ),
    )


def cancel_subscription_for_user(
    db: Session,
    *,
    user: Any,
    cancel_mode: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = _extract_user_id(user)
    email = _extract_user_email(user)
    base_plan = _extract_user_plan(user)

    remote = cancel_subscription_remote(
        email=email,
        cancel_mode=cancel_mode,
        user_id=user_id,
        reason=reason,
    )

    if _normalize_cancel_mode(cancel_mode) == 'immediate':
        local = sync_local_subscription_state(
            db,
            user_id=user_id,
            plan=DEFAULT_PLAN,
            reset_usage=True,
            source='auth_cancel_immediate',
        )
    else:
        local = {
            'ok': True,
            'user_id': user_id,
            'plan': base_plan,
            'tokens_limit': _limit_for_plan(base_plan),
            'quota_features_updated': [],
            'reset_usage': False,
            'source': 'auth_cancel_end_of_period_pending_webhook',
        }

    return {
        'ok': True,
        'user_id': user_id,
        'email': email,
        'cancel_mode': _normalize_cancel_mode(cancel_mode),
        'remote': remote,
        'local': local,
    }


def _extract_event_name(event_name: Any, payload: Dict[str, Any]) -> str:
    raw = str(event_name or payload.get('event') or payload.get('type') or payload.get('name') or '').strip().upper()
    return raw.replace(' ', '_').replace('-', '_')


def _extract_payload_email(payload: Dict[str, Any]) -> str:
    customer = payload.get('customer') or {}
    contact = payload.get('contact') or {}
    for value in (
        customer.get('email'),
        contact.get('email'),
        payload.get('email'),
        payload.get('customer_email'),
    ):
        clean = str(value or '').strip().lower()
        if clean:
            return clean
    return ''


def _extract_priceplan_id(payload: Dict[str, Any]) -> Optional[int]:
    candidates = [
        (payload.get('pricePlan') or {}).get('id'),
        (payload.get('price_plan') or {}).get('id'),
        payload.get('pricePlanId'),
        payload.get('price_plan_id'),
        payload.get('offer_id'),
    ]
    for candidate in candidates:
        try:
            if candidate is not None and str(candidate).strip() != '':
                return int(candidate)
        except Exception:
            pass
    return None


def _get_user_id_by_email(db: Session, email: str) -> Optional[int]:
    row = db.execute(
        text('SELECT id FROM users WHERE LOWER(email) = LOWER(:email) ORDER BY id DESC LIMIT 1'),
        {'email': str(email or '').strip().lower()},
    ).fetchone()
    return int(row[0]) if row else None


def apply_webhook_event(
    db: Session,
    *,
    payload: Dict[str, Any],
    event_name: Any,
) -> Dict[str, Any]:
    normalized_event = _extract_event_name(event_name, payload)
    email = _extract_payload_email(payload)
    if not email:
        raise HTTPException(status_code=400, detail='Missing email')

    user_id = _get_user_id_by_email(db, email)
    if not user_id:
        return {
            'status': 'ignored',
            'reason': 'user_not_found',
            'email': email,
            'event': normalized_event,
        }

    if normalized_event in {'NEW_SALE', 'SALE_COMPLETED', 'PURCHASE'}:
        plan = plan_from_priceplan_id(_extract_priceplan_id(payload))
        if not plan:
            return {
                'status': 'ignored',
                'reason': 'unknown_plan',
                'email': email,
                'user_id': user_id,
                'event': normalized_event,
            }
        result = sync_local_subscription_state(
            db,
            user_id=user_id,
            plan=plan,
            reset_usage=True,
            source='systeme_webhook_new_sale',
        )
        return {
            'status': 'success',
            'email': email,
            'event': normalized_event,
            **result,
        }

    if normalized_event in {'SALE_CANCELED', 'SALE_CANCELLED', 'SUBSCRIPTION_CANCELED', 'SUBSCRIPTION_CANCELLED'}:
        result = sync_local_subscription_state(
            db,
            user_id=user_id,
            plan=DEFAULT_PLAN,
            reset_usage=True,
            source='systeme_webhook_sale_canceled',
        )
        return {
            'status': 'canceled',
            'email': email,
            'event': normalized_event,
            **result,
        }

    if normalized_event in {'SUBSCRIPTION_PAYMENT_FAILED', 'PAYMENT_FAILED'}:
        return {
            'status': 'received',
            'email': email,
            'user_id': user_id,
            'event': normalized_event,
        }

    return {
        'status': 'ignored',
        'email': email,
        'user_id': user_id,
        'event': normalized_event,
    }
