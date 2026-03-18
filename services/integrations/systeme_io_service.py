from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _slugify(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("_", "-")
    text = re.sub(r"[^a-z0-9\- ]+", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "emailing-ia"


def _normalize_mode(mode: Any) -> str:
    allowed = {"draft", "ready", "payload"}
    normalized = _clean_text(mode).lower()
    return normalized if normalized in allowed else "ready"


def _normalize_tag(value: Any) -> str | None:
    tag = _slugify(value)
    return tag if tag else None


def _dedupe_tags(tags: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []

    for tag in tags:
        clean = _normalize_tag(tag)
        if not clean:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        result.append(clean)

    return result


def _normalize_email_item(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    day = item.get("day", index + 1)
    try:
        day = int(day)
    except Exception:
        day = index + 1

    day = max(1, day)

    subject = _clean_text(item.get("subject"))
    preheader = _clean_text(item.get("preheader"))
    body = str(item.get("body") or "").strip()
    cta = _clean_text(item.get("cta"))
    email_type = _clean_text(item.get("email_type")) or "nurture"

    return {
        "position": index + 1,
        "day": day,
        "delay_days": max(0, day - 1),
        "email_type": email_type,
        "subject": subject,
        "preheader": preheader,
        "body": body,
        "cta": cta,
        "name": f"J{day} - {subject[:80] or f'Email {index + 1}'}",
        "stats": {
            "subject_length": len(subject),
            "preheader_length": len(preheader),
            "body_length": len(body),
            "cta_length": len(cta),
        },
    }


def _normalize_sequence(sequence: Dict[str, Any]) -> List[Dict[str, Any]]:
    emails = sequence.get("emails", []) if isinstance(sequence, dict) else []
    if not isinstance(emails, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(emails):
        if not isinstance(item, dict):
            continue
        normalized.append(_normalize_email_item(item, index))

    return normalized


def _build_tags(*, campaign: Any, systeme_tag: str | None, campaign_slug: str) -> List[str]:
    tags: List[str] = [
        "lgd-src-emailing-ia",
        f"lgd-campaign-{campaign_slug}",
    ]

    campaign_type = _slugify(getattr(campaign, "campaign_type", None))
    if campaign_type:
        tags.append(f"lgd-type-{campaign_type}")

    offer_name = _slugify(getattr(campaign, "offer_name", None))
    if offer_name:
        tags.append(f"lgd-offer-{offer_name}")

    tone = _slugify(getattr(campaign, "tone", None))
    if tone:
        tags.append(f"lgd-tone-{tone}")

    sales_intensity = _slugify(getattr(campaign, "sales_intensity", None))
    if sales_intensity:
        tags.append(f"lgd-intensity-{sales_intensity}")

    custom_tag = _normalize_tag(systeme_tag)
    if custom_tag:
        tags.append(custom_tag)

    return _dedupe_tags(tags)


def _build_contact_strategy(tags: List[str]) -> Dict[str, Any]:
    return {
        "provider_entity": "contact",
        "create_or_update_contact": True,
        "attach_tags": True,
        "remove_tags": [],
        "tags_to_apply": tags,
        "recommended_fields": [
            "email",
            "first_name",
            "last_name",
            "phone",
        ],
    }


def _build_campaign_strategy(systeme_campaign_name: str, campaign_slug: str) -> Dict[str, Any]:
    return {
        "provider_entity": "campaign",
        "campaign_name": systeme_campaign_name,
        "campaign_slug": campaign_slug,
        "strategy": "tag_to_workflow_to_campaign",
        "note": (
            "LGD prépare d'abord le contact et les tags. "
            "L'inscription réelle à la campagne doit ensuite être pilotée "
            "par une automatisation Systeme.io basée sur tag/workflow."
        ),
    }


def _build_workflow_strategy(tags: List[str], campaign_slug: str) -> Dict[str, Any]:
    trigger_tag = next((tag for tag in tags if tag.startswith("lgd-campaign-")), f"lgd-campaign-{campaign_slug}")

    return {
        "provider_entity": "workflow",
        "recommended_trigger": "tag_added",
        "trigger_tag": trigger_tag,
        "recommended_workflow_name": f"LGD - Emailing IA - {campaign_slug}",
        "recommended_actions": [
            "subscribe_contact_to_campaign",
            "optional_additional_tags",
            "optional_webhook_callback_to_lgd",
        ],
    }


def _build_webhook_strategy(campaign_slug: str) -> Dict[str, Any]:
    return {
        "provider_entity": "webhook",
        "enabled_in_lgd_payload": False,
        "direction": "systeme_io_to_lgd",
        "recommended_events": [
            "contact_tagged",
            "contact_entered_workflow",
            "campaign_subscription_started",
        ],
        "recommended_topic": f"lgd-emailing-{campaign_slug}",
    }


def build_systeme_io_payload(
    *,
    campaign: Any,
    sequence: Dict[str, Any],
    systeme_tag: str | None,
    systeme_campaign_name: str | None,
    mode: str,
) -> Dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
    normalized_sequence = _normalize_sequence(sequence)

    campaign_name = _clean_text(getattr(campaign, "name", None)) or "Campagne Emailing IA"
    campaign_slug = _slugify(campaign_name)

    final_systeme_campaign_name = (
        _clean_text(systeme_campaign_name)
        or _clean_text(getattr(campaign, "systeme_campaign_name", None))
        or campaign_name
    )

    final_systeme_tag = (
        _normalize_tag(systeme_tag)
        or _normalize_tag(getattr(campaign, "systeme_tag", None))
    )

    tags = _build_tags(
        campaign=campaign,
        systeme_tag=final_systeme_tag,
        campaign_slug=campaign_slug,
    )

    email_count = len(normalized_sequence)
    ready_for_push = normalized_mode in {"ready", "payload"}

    return {
        "provider": "systeme_io",
        "prepared_at": datetime.utcnow().isoformat(),
        "mode": normalized_mode,
        "campaign": {
            "internal_id": getattr(campaign, "id", None),
            "name": campaign_name,
            "slug": campaign_slug,
            "type": _clean_text(getattr(campaign, "campaign_type", None)),
            "duration_days": getattr(campaign, "duration_days", None),
            "sender_name": _clean_text(getattr(campaign, "sender_name", None)),
            "offer_name": _clean_text(getattr(campaign, "offer_name", None)),
            "target_audience": _clean_text(getattr(campaign, "target_audience", None)),
            "main_promise": _clean_text(getattr(campaign, "main_promise", None)),
            "main_objective": _clean_text(getattr(campaign, "main_objective", None)),
            "primary_cta": _clean_text(getattr(campaign, "primary_cta", None)),
            "tone": _clean_text(getattr(campaign, "tone", None)),
            "sales_intensity": _clean_text(getattr(campaign, "sales_intensity", None)),
            "systeme_campaign_name": final_systeme_campaign_name,
            "tag": final_systeme_tag,
            "tags": tags,
        },
        "sequence": normalized_sequence,
        "contact_strategy": _build_contact_strategy(tags),
        "campaign_strategy": _build_campaign_strategy(final_systeme_campaign_name, campaign_slug),
        "workflow_strategy": _build_workflow_strategy(tags, campaign_slug),
        "webhook_strategy": _build_webhook_strategy(campaign_slug),
        "meta": {
            "ready_for_push": ready_for_push,
            "email_count": email_count,
            "source_module": "lgd_emailing_ia",
            "architecture_version": "systeme_io_v1",
            "planner_scope": "email_only",
            "safe_for_social_planner": True,
        },
    }
