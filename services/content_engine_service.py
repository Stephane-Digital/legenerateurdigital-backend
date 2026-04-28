# C:\LGD\legenerateurdigital_backend\services\content_engine_service.py

import os
from openai import OpenAI
from config.settings import settings

# ============================================================
# INITIALISATION OPENAI (v1+)
# ============================================================

def _get_api_key() -> str:
    # Priorité: env > settings
    key = os.getenv("OPENAI_API_KEY", "").strip() or str(getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    return key


def _get_model(default: str = "gpt-4o-mini") -> str:
    # Tu peux override sans toucher au code :
    # OPENAI_MODEL=gpt-4o-mini
    # OPENAI_MODEL_REWRITE=gpt-4o-mini
    # OPENAI_MODEL_SUMMARY=gpt-4o-mini
    return (default or "gpt-4o-mini").strip()


def _client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise Exception("OPENAI_API_KEY manquante (dans .env ou settings)")
    return OpenAI(api_key=api_key)


def _extract_text(resp) -> str:
    try:
        out = (resp.choices[0].message.content or "").strip()
        return out
    except Exception:
        return ""


# ============================================================
# 🧠 GENERATE AI TEXT
# ============================================================
def generate_ai_text(prompt: str, tone: str = "default", language: str = "fr") -> str:
    """
    Génère un texte avec l'IA en fonction du prompt.
    Compatible openai>=1.0.0
    """

    system_prompt = (
        "Tu es l'IA premium de Le Générateur Digital (LGD), spécialisée en marketing digital, "
        "copywriting direct response, storytelling, conversion et pédagogie business. "
        f"Tu écris toujours en langue : {language}. "
        f"Ton demandé : {tone}. "
        "Avant d'écrire, tu raisonnes silencieusement comme un stratège : cible, douleur, désir, objection, promesse, preuve, CTA. "
        "Tu ne montres jamais cette analyse sauf si l'utilisateur la demande. "
        "Tu produis ensuite un contenu final humain, clair, concret, crédible, premium et orienté action. "
        "Évite les formulations génériques, le ton robotique, les promesses irréalistes et la copie mot à mot. "
        "Réécris toujours de façon originale : inspiré par les mécaniques de conversion, jamais par duplication."
    )

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL", "").strip() or os.getenv("OPENAI_MODEL_TEXT", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.72,
            max_tokens=750,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur AI Text: {str(e)}")


# ============================================================
# ✍️ REWRITE TEXT
# ============================================================
def rewrite_text(text: str, tone: str | None = None, max_length: int | None = None) -> str:
    """
    Réécrit un texte en version améliorée, plus claire et professionnelle.

    ✅ LGD FIX:
    - Supporte tone + max_length (optionnels) sans casser l'ancienne signature.
    - Compatible openai>=1.0.0
    """

    tone_txt = (tone or "").strip()
    max_len = int(max_length) if max_length is not None else None

    instr = (
        "Réécris ce texte en version LGD premium : plus humain, plus clair, plus orienté conversion, "
        "sans perdre le sens original. Améliore le hook, la fluidité, les bénéfices, le rythme et le CTA si présent. "
        "Ne copie pas mécaniquement : reformule proprement, avec une voix naturelle et crédible."
    )
    if tone_txt:
        instr += f" Adopte un ton: {tone_txt}."
    if max_len and max_len > 0:
        instr += f" Limite-toi à environ {max_len} caractères."

    user_prompt = f"{instr}\n\nTEXTE À RÉÉCRIRE :\n{text}"

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL_REWRITE", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un copywriter senior LGD. Tu transformes un texte brut en version premium, humaine, persuasive et originale, sans copier ni surpromettre."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur Rewrite: {str(e)}")


# ============================================================
# 📝 SUMMARIZE TEXT
# ============================================================
def summarize_text(text: str) -> str:
    """
    Produit un résumé clair et concis du texte fourni.
    Compatible openai>=1.0.0
    """
    prompt = f"Résume ce texte en 5 lignes maximum :\n\n{text}"

    # Modèle configurable sans toucher au code
    model = os.getenv("OPENAI_MODEL_SUMMARY", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en synthèse."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=200,
        )

        out = _extract_text(response)
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur Résumé: {str(e)}")


# ============================================================
# 📣 GENERATE SOCIAL CAPTION
# ============================================================
def generate_social_caption(
    *,
    prompt: str | None = None,
    brief: str | None = None,
    network: str | None = None,
    tone: str | None = None,
    objective: str | None = None,
    audience: str | None = None,
    brand_name: str | None = None,
    offer_name: str | None = None,
    language: str = "fr",
    media_type: str | None = None,
    post_type: str | None = None,
    context: str | None = None,
    existing_caption: str | None = None,
    include_hashtags: bool = False,
    include_cta: bool = False,
) -> str:
    """
    Génère une légende/caption prête à publier pour les réseaux sociaux.

    Objectif LGD:
    - réponse simple à brancher dans AssistedPublishModal
    - caption premium, claire, naturelle, orientée conversion
    - hashtags/CTA optionnels selon les boutons frontend
    """

    parts = [
        str(prompt or "").strip(),
        str(brief or "").strip(),
        str(context or "").strip(),
        str(existing_caption or "").strip(),
        str(objective or "").strip(),
        str(audience or "").strip(),
        str(brand_name or "").strip(),
        str(offer_name or "").strip(),
    ]
    if not any(parts):
        raise ValueError("Aucun contexte fourni pour générer la caption.")

    network_txt = (network or "réseau social").strip()
    tone_txt = (tone or "premium, humain et engageant").strip()
    objective_txt = (objective or "engager et convertir").strip()
    audience_txt = (audience or "audience froide ou tiède").strip()
    brand_txt = (brand_name or "LGD").strip()
    offer_txt = (offer_name or "offre").strip()
    media_txt = (media_type or "publication").strip()
    post_type_txt = (post_type or "post").strip()
    lang = (language or "fr").strip()

    system_prompt = (
        "Tu es le Social Content Strategist premium de Le Générateur Digital (LGD). "
        "Tu crées des captions originales qui analysent silencieusement l'audience, l'angle, la promesse, "
        "l'objection et le format du réseau avant d'écrire. "
        "Tu rédiges des contenus naturels, humains, rythmés, concrets, avec une mécanique de conversion claire "
        "sans ressembler à une IA générique. "
        f"Tu écris toujours en {lang}. "
        "Ne renvoie que la caption finale, sans titre, sans explication, sans JSON, sans balises markdown. "
        "Ne copie jamais mot à mot une base existante : transforme l'angle et reformule complètement."
    )

    instruction_blocks = [
        f"Réseau: {network_txt}",
        f"Ton: {tone_txt}",
        f"Objectif: {objective_txt}",
        f"Audience: {audience_txt}",
        f"Marque: {brand_txt}",
        f"Offre: {offer_txt}",
        f"Type de contenu: {post_type_txt}",
        f"Type de média: {media_txt}",
    ]

    content_blocks = []
    if prompt:
        content_blocks.append(f"Prompt principal:\n{str(prompt).strip()}")
    if brief:
        content_blocks.append(f"Brief:\n{str(brief).strip()}")
    if context:
        content_blocks.append(f"Contexte additionnel:\n{str(context).strip()}")
    if existing_caption:
        content_blocks.append(
            f"Base existante à améliorer/régénérer sans la recopier mot à mot:\n{str(existing_caption).strip()}"
        )

    option_lines = [
        "Longueur cible: entre 80 et 220 mots maximum selon le sujet.",
        "Structure: hook fort dès la première ligne, tension/problème, valeur concrète, transition, fin propre.",
        "Ajoute une micro-rupture ou un angle original pour éviter le contenu plat.",
        "Évite les emojis excessifs, les formulations génériques et les phrases trop longues.",
        "Privilégie le 'tu' si le contexte le permet, sinon reste premium et direct.",
    ]
    if include_hashtags:
        option_lines.append("Ajoute 5 à 10 hashtags pertinents en fin de caption.")
    else:
        option_lines.append("N'ajoute aucun hashtag.")

    if include_cta:
        option_lines.append("Ajoute un CTA discret, premium et orienté action en fin de caption.")
    else:
        option_lines.append("N'ajoute pas de CTA explicite.")

    user_prompt = (
        "Génère une caption sociale prête à publier.\n\n"
        + "\n".join(instruction_blocks)
        + "\n\n"
        + "\n\n".join(content_blocks)
        + "\n\nContraintes:\n- "
        + "\n- ".join(option_lines)
    )

    model = (
        os.getenv("OPENAI_MODEL_CAPTION", "").strip()
        or os.getenv("OPENAI_MODEL_TEXT", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )
    model = _get_model(model)

    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=500,
        )

        out = _extract_text(response)
        out = (out or "").strip().strip('"').strip()
        if not out:
            raise Exception("Réponse OpenAI vide")
        return out

    except Exception as e:
        raise Exception(f"Erreur Caption IA: {str(e)}")
