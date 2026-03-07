from schemas.social_post_ai_schema import SocialPostAIGenerateRequest, SocialPostAIResponse


# Base de "styles" pré-IA pour chaque réseau
NETWORK_PROFILES = {
    "TikTok": {
        "hook": "🔥 Astuce exclusive",
        "style": "Court, dynamique, viral, orienté accroche.",
        "ending": "➡️ Sauvegarde ce post si tu veux une partie 2 !",
    },
    "Instagram": {
        "hook": "📸 Petite histoire…",
        "style": "Storytelling court, humain, émotionnel.",
        "ending": "#entrepreneuriat #business #digital",
    },
    "LinkedIn": {
        "hook": "💼 Insight pro :",
        "style": "Structuré, professionnel, orienté valeur.",
        "ending": "👉 Et vous, qu’en pensez-vous ?",
    },
    "Facebook": {
        "hook": "👋 Hé la team,",
        "style": "Ton convivial, discussion naturelle.",
        "ending": "Dites-moi en commentaires !",
    },
    "X (Twitter)": {
        "hook": "⚡ Idée rapide :",
        "style": "Direct, concis, punchline.",
        "ending": "#Marketing #IA #Growth",
    },
    "YouTube": {
        "hook": "🎥 Conseil rapide :",
        "style": "Éducatif, clair, pratique.",
        "ending": "Abonne-toi pour la suite 🎯",
    },
    "Pinterest": {
        "hook": "📌 Inspiration :",
        "style": "Visuel, lifestyle, motivationnel.",
        "ending": "#design #inspiration #digital",
    },
}


def generate_social_post(data: SocialPostAIGenerateRequest) -> SocialPostAIResponse:
    reseau = data.reseau
    sujet = data.sujet
    objectif = data.objectif or "partager une idée"
    tonalite = data.tonalite or "simple et engageante"

    profile = NETWORK_PROFILES.get(reseau, NETWORK_PROFILES["Facebook"])

    texte = (
        f"{profile['hook']} {sujet}\n\n"
        f"Objectif : {objectif}.\n"
        f"Style : {profile['style']} Tonalité : {tonalite}.\n\n"
        f"{profile['ending']}"
    )

    return SocialPostAIResponse(
        texte=texte,
        reseau=reseau
    )
