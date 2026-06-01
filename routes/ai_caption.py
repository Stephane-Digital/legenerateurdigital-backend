from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import get_or_create_quota
from services.ai_quota_service import update_quota

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


router = APIRouter(prefix="/ai-caption", tags=["AI Caption"])


class CaptionRequest(BaseModel):
    prompt: str
    network: str = "instagram"
    tone: str = "premium"
    objective: str = "conversion"
    existing_caption: Optional[str] = None
    include_hashtags: bool = False
    include_cta: bool = False
    language: str = "fr"
    post_type: str = "post"
    media_type: str = "image"


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").replace("\r", " ").strip().split())


def _clean_multiline(value: str | None) -> str:
    text = str(value or "").replace("\r", "").strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def _capitalize_first(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    return value[0].upper() + value[1:]


def _choose_model() -> str:
    return (
        os.getenv("OPENAI_CAPTION_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _get_openai_client() -> Optional["OpenAI"]:
    if OpenAI is None:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    return OpenAI(api_key=api_key)


def _source_from_prompt(prompt: str) -> str:
    """
    Frontend sends a structured prompt containing the real content detected in
    the post/layers. We extract that core content so fallback hashtags/CTA do not
    use technical labels like "RÈGLES STRICTES".
    """
    text = _clean_multiline(prompt)
    if not text:
        return ""

    marker = "Texte réel détecté dans le post / visuel / layers / Performeur Réseaux :"
    rules = "RÈGLES STRICTES :"

    if marker in text:
        text = text.split(marker, 1)[1].strip()

    if rules in text:
        text = text.split(rules, 1)[0].strip()

    # Remove common meta lines while preserving the actual post text.
    kept: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        lower = clean.lower()
        if lower.startswith("source réelle"):
            continue
        if lower.startswith("titre :"):
            continue
        if lower.startswith("réseau :"):
            continue
        if lower.startswith("ton demandé :"):
            continue
        if lower.startswith("objectif :"):
            continue
        kept.append(clean)

    return _clean_multiline("\n".join(kept)) or _clean_text(prompt)


def _infer_keywords(prompt: str) -> list[str]:
    source = _source_from_prompt(prompt)
    words = (
        source.lower()
        .replace("\n", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(";", " ")
        .replace(":", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace("’", "'")
        .split()
    )

    stopwords = {
        "avec", "pour", "dans", "les", "des", "une", "sur", "que", "qui",
        "est", "pas", "plus", "vous", "nous", "leur", "leurs", "votre",
        "notre", "cette", "cet", "cela", "comme", "mais", "par", "sans",
        "tout", "tous", "toute", "toutes", "elle", "elles", "il", "ils",
        "the", "and", "your", "this", "that", "from", "into", "au",
        "aux", "de", "du", "la", "le", "un", "en", "ou", "et", "à", "d",
        "source", "réelle", "publication", "texte", "détecté", "post",
        "visuel", "layers", "performeur", "réseaux", "titre", "objectif",
    }

    keywords: list[str] = []
    seen = set()

    for word in words:
        cleaned = "".join(ch for ch in word if ch.isalnum() or ch in "àâäéèêëîïôöùûüç")
        if len(cleaned) < 4:
            continue
        if cleaned in stopwords:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        keywords.append(cleaned)
        if len(keywords) >= 6:
            break

    return keywords


def _hashtags_for_network(network: str) -> list[str]:
    network = network.lower().strip()
    mapping = {
        "instagram": ["#instagram", "#contenu"],
        "facebook": ["#facebook", "#communaute"],
        "linkedin": ["#linkedin", "#personalbranding"],
        "pinterest": ["#pinterest", "#inspiration"],
        "snapchat": ["#snapchat", "#contenu"],
        "tiktok": ["#tiktok", "#creationdecontenu"],
    }
    return mapping.get(network, ["#socialmedia", "#contenu"])


def _hashtags_for_objective(objective: str) -> list[str]:
    objective = objective.lower().strip()
    mapping = {
        "conversion": ["#conversion", "#passagealaction"],
        "engagement": ["#engagement", "#communaute"],
        "lead": ["#prospection", "#leads"],
        "visibility": ["#visibilite", "#notoriete"],
    }
    return mapping.get(objective, ["#strategie", "#action"])


def build_dynamic_hashtags(data: CaptionRequest) -> str:
    keywords = _infer_keywords(data.prompt)
    keyword_tags = [f"#{word}" for word in keywords[:5]]

    tags = [
        *keyword_tags,
        *_hashtags_for_network(data.network),
        *_hashtags_for_objective(data.objective),
    ]

    unique_tags: list[str] = []
    seen = set()
    for tag in tags:
        t = tag.strip()
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        unique_tags.append(t)

    return " ".join(unique_tags[:8])


def build_cta(data: CaptionRequest) -> str:
    objective = data.objective.lower().strip()
    network = data.network.lower().strip()

    if objective == "conversion":
        return "👉 Passe à l’action aujourd’hui et applique ce conseil dès maintenant."
    if objective == "engagement":
        return (
            "👉 Dis-moi en commentaire ce que tu en penses."
            if network != "linkedin"
            else "👉 Partage ton avis en commentaire : je veux lire ton retour."
        )
    if objective == "lead":
        return "👉 Écris-moi en message privé si tu veux aller plus loin."
    if objective == "visibility":
        return "👉 Enregistre cette publication pour y revenir plus tard."
    return "👉 Passe à l’action dès aujourd’hui."


def _fallback_caption(data: CaptionRequest, cta_text: str = "", hashtags_text: str = "") -> str:
    source = _source_from_prompt(data.prompt)
    safe_source = _capitalize_first(_clean_text(source)) or "Cette publication"

    tone = data.tone.lower().strip()
    objective = data.objective.lower().strip()

    if tone == "direct":
        opener = "Allons droit au but."
    elif tone == "expert":
        opener = "Voici l’idée à retenir."
    elif tone == "inspirant":
        opener = "Parfois, un simple rappel peut changer ta façon d’agir."
    else:
        opener = "Un bon visuel mérite une légende claire et alignée."

    if objective == "engagement":
        angle = "Le but ici est d’ouvrir la discussion et de donner envie de réagir."
    elif objective == "lead":
        angle = "Le but ici est de créer une connexion naturelle avec les bonnes personnes."
    elif objective == "visibility":
        angle = "Le but ici est de rendre le message plus lisible, plus mémorable et plus partageable."
    else:
        angle = "Le but ici est de transformer l’attention en action concrète."

    caption = "\n\n".join(
        [
            opener,
            safe_source,
            angle,
        ]
    )

    if cta_text:
        caption = f"{caption}\n\n{cta_text}"
    if hashtags_text:
        caption = f"{caption}\n\n{hashtags_text}"

    return caption.strip()


def _build_live_prompt(data: CaptionRequest, *, cta_text: str = "", hashtags_text: str = "") -> str:
    source = _source_from_prompt(data.prompt)
    existing = _clean_multiline(data.existing_caption)

    task = "Génère une légende social media en français."
    if data.include_hashtags:
        task = "Renvoie uniquement des hashtags pertinents en français, séparés par des espaces."
    elif data.include_cta:
        task = "Renvoie uniquement un CTA final en français, sur une seule ligne."

    return f"""
MISSION
{task}

SOURCE RÉELLE À RESPECTER
{source or data.prompt}

PARAMÈTRES
- Réseau : {data.network}
- Ton : {data.tone}
- Objectif : {data.objective}
- Type de post : {data.post_type}
- Type média : {data.media_type}
- Légende existante éventuelle : {existing or "aucune"}

RÈGLES ABSOLUES
- Reste strictement aligné avec la source réelle.
- N'invente pas un sujet différent.
- Ne parle jamais de MRR, LGD, formation, business, présentation mobile ou outil digital si la source ne le mentionne pas clairement.
- Si la source parle de yoga, concentration, bien-être, santé ou tout autre sujet, reste sur ce sujet.
- Style humain, clair, prêt à publier.
- Pas de titre "Voici..." sauf si nécessaire.
- Pas de markdown.
- Pas de guillemets autour de la réponse.
- Si hashtags imposés : {hashtags_text or "aucun hashtag imposé"}.
- Si CTA imposé : {cta_text or "aucun CTA imposé"}.
""".strip()


def _generate_live_caption(data: CaptionRequest, *, cta_text: str = "", hashtags_text: str = "") -> Optional[str]:
    client = _get_openai_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=_choose_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es l'IA Caption Generator de Le Générateur Digital. "
                        "Tu génères des légendes social media strictement alignées avec le contenu réel fourni. "
                        "Tu n'inventes jamais un autre sujet."
                    ),
                },
                {"role": "user", "content": _build_live_prompt(data, cta_text=cta_text, hashtags_text=hashtags_text)},
            ],
            temperature=0.68,
            max_tokens=650 if not (data.include_hashtags or data.include_cta) else 220,
        )

        content = (response.choices[0].message.content or "").strip()
        return _clean_multiline(content) if content else None
    except Exception:
        return None


@router.post("/generate")
def generate_caption(
    payload: CaptionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = int(user["id"] if isinstance(user, dict) else user.id)

    quota = get_or_create_quota(db, user_id, feature="coach")

    remaining = max(
        int(getattr(quota, "credits", 0)) - int(getattr(quota, "tokens_used", 0)),
        0,
    )

    if remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {"message": "Quota IA épuisé. Passe au plan supérieur."},
            },
        )

    updated = update_quota(db, user_id, 1, feature="coach")

    if updated is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {"message": "Quota IA épuisé. Passe au plan supérieur."},
            },
        )

    new_remaining = max(
        int(getattr(updated, "credits", 0)) - int(getattr(updated, "tokens_used", 0)),
        0,
    )

    cta_text = build_cta(payload) if payload.include_cta else ""
    hashtags_text = build_dynamic_hashtags(payload) if payload.include_hashtags else ""

    live_caption = _generate_live_caption(payload, cta_text=cta_text, hashtags_text=hashtags_text)
    caption = live_caption or _fallback_caption(payload, cta_text=cta_text, hashtags_text=hashtags_text)

    return {
        "caption": caption,
        "cta": cta_text,
        "hashtags": hashtags_text,
        "quota": {"remaining": new_remaining},
        "upsell": {
            "show": new_remaining <= 5,
            "message": "⚡ Plus que quelques crédits IA disponibles." if new_remaining <= 5 else "",
        },
    }
