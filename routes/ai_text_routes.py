from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.content_engine_service import generate_social_caption, rewrite_text
from services.ai_quota_service import get_or_create_quota, update_quota
from services.user_entitlements import get_effective_plan

router = APIRouter(tags=["AI Text"])


# ============================================================
# 📌 PAYLOADS
# ============================================================
class RewritePayload(BaseModel):
    text: str
    tone: Optional[str] = None
    max_length: Optional[int] = None


class CaptionGeneratePayload(BaseModel):
    prompt: Optional[str] = None
    brief: Optional[str] = None
    network: Optional[str] = None
    tone: Optional[str] = None
    objective: Optional[str] = None
    audience: Optional[str] = None
    brand_name: Optional[str] = None
    offer_name: Optional[str] = None
    language: Optional[str] = "fr"
    media_type: Optional[str] = None
    post_type: Optional[str] = None
    context: Optional[str] = None
    existing_caption: Optional[str] = None
    include_hashtags: bool = False
    include_cta: bool = False


# ============================================================
# 🔧 HELPERS
# ============================================================
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


def _user_id(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(getattr(user, "id"))


def _user_base_plan(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("plan") or "essentiel")
    return str(getattr(user, "plan", None) or "essentiel")


def _effective_plan(db: Session, user: Any) -> str:
    try:
        plan, _ov = get_effective_plan(
            db,
            user_id=_user_id(user),
            base_plan=_user_base_plan(user),
        )
        return str(plan or _user_base_plan(user))
    except Exception:
        return _user_base_plan(user)


def _limit_for_plan(plan: str) -> int:
    p = str(plan or "essentiel").lower()
    if "ult" in p:
        return 2_500_000
    if "pro" in p:
        return 1_000_000
    return 400_000


def _quota_snapshot(quota: Any, *, plan_override: Optional[str] = None) -> dict:
    plan = str(plan_override or getattr(quota, "plan", None) or "essentiel")

    used = _to_int(getattr(quota, "tokens_used", None), 0)
    if used == 0 and getattr(quota, "used_tokens", None) is not None:
        used = _to_int(getattr(quota, "used_tokens", None), 0)

    limit = _to_int(getattr(quota, "credits", None), 0)
    if limit == 0 and getattr(quota, "tokens_limit", None) is not None:
        limit = _to_int(getattr(quota, "tokens_limit", None), 0)
    if limit == 0 and getattr(quota, "limit_tokens", None) is not None:
        limit = _to_int(getattr(quota, "limit_tokens", None), 0)
    if limit <= 0:
        limit = _limit_for_plan(plan)

    remaining = _to_int(getattr(quota, "remaining", None), max(limit - used, 0))
    if remaining < 0:
        remaining = max(limit - used, 0)

    return {
        "feature": "global",
        "plan": plan,
        "tokens_used": used,
        "tokens_limit": limit,
        "remaining": remaining,
    }


def _estimate_tokens(*parts: Any) -> int:
    text = " ".join([str(p or "") for p in parts]).strip()
    return max(1, int(len(text) / 4))


def _upsell_payload(plan: str, remaining: int) -> dict:
    norm = str(plan or "essentiel").lower()
    next_plan = "pro" if norm == "essentiel" else "ultime"

    return {
        "show": remaining <= 0,
        "current_plan": norm,
        "suggested_plan": next_plan,
        "title": "Quota IA atteint",
        "message": "Votre quota IA est épuisé. Passez au plan supérieur pour continuer à générer vos captions sans blocage.",
        "cta_label": f"Passer à {next_plan.capitalize()}",
    }


def _safe_prompt_present(payload: CaptionGeneratePayload) -> bool:
    values = [
        payload.prompt,
        payload.brief,
        payload.context,
        payload.existing_caption,
        payload.objective,
        payload.audience,
        payload.brand_name,
        payload.offer_name,
    ]
    return any(str(v or "").strip() for v in values)


# ============================================================
# 🧠 RÉÉCRITURE TEXTE
# ============================================================
@router.post("/ai/text/rewrite")
def ai_rewrite_text(
    payload: RewritePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide.")

    result = rewrite_text(
        text=payload.text,
        tone=payload.tone,
        max_length=payload.max_length,
    )

    return {"result": result}


# ============================================================
# 📣 IA CAPTION GENERATOR V2 — BRANCHEMENT RÉEL
# ============================================================
@router.post("/ai-caption/generate")
def ai_generate_caption(
    payload: CaptionGeneratePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _safe_prompt_present(payload):
        raise HTTPException(status_code=400, detail="Le contexte de génération est vide.")

    user_id = _user_id(user)
    effective_plan = _effective_plan(db, user)

    # ✅ Quota global centralisé LGD
    quota = get_or_create_quota(db, user_id, feature="global")
    snap_before = _quota_snapshot(quota, plan_override=effective_plan)

    if _to_int(snap_before.get("remaining"), 0) <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "QUOTA_REACHED",
                "message": "Votre quota IA est épuisé pour ce mois.",
                "quota": snap_before,
                "upsell": _upsell_payload(effective_plan, 0),
            },
        )

    try:
        caption = generate_social_caption(
            prompt=payload.prompt,
            brief=payload.brief,
            network=payload.network,
            tone=payload.tone,
            objective=payload.objective,
            audience=payload.audience,
            brand_name=payload.brand_name,
            offer_name=payload.offer_name,
            language=payload.language or "fr",
            media_type=payload.media_type,
            post_type=payload.post_type,
            context=payload.context,
            existing_caption=payload.existing_caption,
            include_hashtags=bool(payload.include_hashtags),
            include_cta=bool(payload.include_cta),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI_CAPTION_GENERATION_ERROR: {exc}",
        ) from exc

    tokens_consumed = _estimate_tokens(
        payload.prompt,
        payload.brief,
        payload.context,
        payload.existing_caption,
        payload.objective,
        payload.audience,
        payload.brand_name,
        payload.offer_name,
        payload.network,
        payload.tone,
        payload.media_type,
        payload.post_type,
        caption,
    )

    updated_quota = update_quota(db, user_id, tokens_consumed, feature="global")

    if updated_quota is None:
        latest_quota = get_or_create_quota(db, user_id, feature="global")
        latest_snap = _quota_snapshot(latest_quota, plan_override=effective_plan)

        raise HTTPException(
            status_code=402,
            detail={
                "code": "QUOTA_REACHED",
                "message": "Le quota IA restant est insuffisant pour cette génération.",
                "quota": latest_snap,
                "upsell": _upsell_payload(
                    effective_plan,
                    _to_int(latest_snap.get("remaining"), 0),
                ),
            },
        )

    snap_after = _quota_snapshot(updated_quota, plan_override=effective_plan)

    return {
        "ok": True,
        "caption": caption,
        "tokens_consumed": tokens_consumed,
        "quota": snap_after,
        "upsell": _upsell_payload(
            effective_plan,
            _to_int(snap_after.get("remaining"), 0),
        ),
        "message": "Caption générée avec succès.",
    }
