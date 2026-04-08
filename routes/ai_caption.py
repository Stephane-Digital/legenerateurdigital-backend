from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user
from services.ai_quota_service import update_quota
from services.ai_quota_service import get_or_create_quota

router = APIRouter(prefix="/ai-caption", tags=["AI Caption"])


class CaptionRequest(BaseModel):
    prompt: str
    network: str = "instagram"
    tone: str = "premium"
    objective: str = "conversion"
    existing_caption: str | None = None
    include_hashtags: bool = False
    include_cta: bool = False
    language: str = "fr"
    post_type: str = "post"
    media_type: str = "image"


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _capitalize_first(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    return value[0].upper() + value[1:]


def _infer_keywords(prompt: str) -> list[str]:
    words = (
        prompt.lower()
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
        "the", "and", "your", "this", "that", "from", "into", "avec", "au",
        "aux", "de", "du", "la", "le", "un", "en", "ou", "et", "à", "d",
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
        if len(keywords) >= 4:
            break

    return keywords


def _hashtags_for_network(network: str) -> list[str]:
    network = network.lower().strip()
    mapping = {
        "instagram": ["#instagrammarketing", "#contenuinstagram"],
        "facebook": ["#facebookmarketing", "#contenusocial"],
        "linkedin": ["#linkedinfr", "#personalbranding"],
        "pinterest": ["#pinterestmarketing", "#visibiliteweb"],
        "snapchat": ["#snapchatbusiness", "#contenudigital"],
    }
    return mapping.get(network, ["#socialmedia", "#marketingdigital"])


def _hashtags_for_objective(objective: str) -> list[str]:
    objective = objective.lower().strip()
    mapping = {
        "conversion": ["#conversion", "#ventes"],
        "engagement": ["#engagement", "#communaute"],
        "lead": ["#generationdeleads", "#prospection"],
        "visibility": ["#visibilite", "#notoriete"],
    }
    return mapping.get(objective, ["#strategie", "#businessenligne"])


def build_dynamic_hashtags(data: CaptionRequest) -> str:
    keywords = _infer_keywords(data.prompt)
    keyword_tags = [f"#{word}" for word in keywords[:4]]

    tags = [
        *keyword_tags,
        *_hashtags_for_network(data.network),
        *_hashtags_for_objective(data.objective),
        "#lgd",
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
        return "👉 Passe à l’action maintenant et transforme cette idée en résultat concret."
    if objective == "engagement":
        return (
            "👉 Dis-moi en commentaire ce que tu en penses"
            if network != "linkedin"
            else "👉 Donne-moi ton avis en commentaire : je veux connaître ton retour."
        )
    if objective == "lead":
        return "👉 Écris-moi en message privé si tu veux attirer plus de prospects qualifiés."
    if objective == "visibility":
        return "👉 Enregistre cette publication et partage-la à quelqu’un qui en a besoin."
    return "👉 Passe à l’action avec LGD."


def build_intro(data: CaptionRequest) -> str:
    tone = data.tone.lower().strip()
    network = data.network.lower().strip()

    if tone == "expert":
        return (
            "Voici un angle plus structuré pour transformer cette idée en message clair et crédible."
        )
    if tone == "inspirant":
        return (
            "Chaque contenu peut devenir un vrai levier de croissance quand le message touche juste."
        )
    if tone == "direct":
        return (
            "Allons droit au but : ton message doit être simple, net et impactant."
        )

    if network == "linkedin":
        return "🚀 Renforce ton positionnement avec une prise de parole claire, utile et premium."
    if network == "facebook":
        return "🚀 Capte l’attention rapidement avec une publication fluide, humaine et engageante."
    if network == "pinterest":
        return "🚀 Donne envie de cliquer avec une description plus claire, inspirante et orientée résultat."
    if network == "snapchat":
        return "🚀 Va à l’essentiel avec un message rapide, fort et mémorable."
    return "🚀 Passe à un niveau supérieur avec une communication plus claire, plus humaine et plus rentable."


def build_body(data: CaptionRequest) -> str:
    network = data.network.lower().strip()

    if network == "linkedin":
        return (
            "Sur LinkedIn, la différence se fait sur la clarté, l’angle stratégique et la valeur perçue."
        )
    if network == "facebook":
        return (
            "Sur Facebook, il faut créer une proximité immédiate, donner envie de lire jusqu’au bout et déclencher l’interaction."
        )
    if network == "pinterest":
        return (
            "Sur Pinterest, une bonne description doit être claire, inspirante et orientée vers une recherche concrète."
        )
    if network == "snapchat":
        return (
            "Sur Snapchat, le message doit aller vite, frapper juste et rester naturel."
        )
    return (
        "Sur Instagram, l’impact visuel doit être soutenu par une légende claire, engageante et bien structurée."
    )


def build_objective_line(data: CaptionRequest) -> str:
    objective = data.objective.lower().strip()

    if objective == "conversion":
        return "L’objectif ici est de créer l’attention, la confiance et le passage à l’action."
    if objective == "engagement":
        return "L’objectif ici est de stimuler les réactions, les enregistrements et les partages."
    if objective == "lead":
        return "L’objectif ici est de transformer l’intérêt en prospect qualifié."
    if objective == "visibility":
        return "L’objectif ici est de renforcer ta visibilité avec un message plus fort et plus lisible."
    return "L’objectif ici est d’améliorer l’impact global de la publication."


def build_variation_line(data: CaptionRequest) -> str:
    prompt = _clean_text(data.prompt)
    existing = _clean_text(data.existing_caption)

    if existing and existing != prompt:
        return (
            "J’ai généré une nouvelle variation pour éviter la répétition et donner un angle plus frais à ta publication."
        )

    if data.post_type.lower().strip() == "carrousel":
        return "Le format carrousel mérite une accroche forte et une lecture fluide d’une slide à l’autre."

    if data.media_type.lower().strip() == "image":
        return "L’idée est d’aligner la promesse du visuel avec une légende qui donne envie d’aller plus loin."

    return "Le texte a été pensé pour rester lisible, premium et immédiatement exploitable."


def generate_caption_text(data: CaptionRequest):
    prompt = _clean_text(data.prompt)
    intro = build_intro(data)
    body = build_body(data)
    objective_line = build_objective_line(data)
    variation_line = build_variation_line(data)

    safe_prompt = _capitalize_first(prompt) if prompt else "Ta publication"

    sections = [
        intro,
        body,
        f'Base de travail : "{safe_prompt}".',
        objective_line,
        variation_line,
    ]

    if data.include_cta:
        sections.append(build_cta(data))

    if data.include_hashtags:
        sections.append(build_dynamic_hashtags(data))

    return "\n\n".join(section for section in sections if section.strip())


@router.post("/generate")
def generate_caption(
    payload: CaptionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = int(user["id"] if isinstance(user, dict) else user.id)

    quota = get_or_create_quota(db, user_id, feature="coach")

    remaining = max(
        int(getattr(quota, "credits", 0))
        - int(getattr(quota, "tokens_used", 0)),
        0,
    )

    if remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {
                    "message": "Quota IA épuisé. Passe au plan supérieur."
                },
            },
        )

    updated = update_quota(db, user_id, 1, feature="coach")

    if updated is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUOTA_REACHED",
                "upsell": {
                    "message": "Quota IA épuisé. Passe au plan supérieur."
                },
            },
        )

    new_remaining = max(
        int(getattr(updated, "credits", 0))
        - int(getattr(updated, "tokens_used", 0)),
        0,
    )

    caption = generate_caption_text(payload)

    return {
        "caption": caption,
        "quota": {
            "remaining": new_remaining
        },
        "upsell": {
            "show": new_remaining <= 5,
            "message": (
                "⚡ Plus que quelques crédits IA disponibles."
                if new_remaining <= 5
                else ""
            ),
        },
    }
