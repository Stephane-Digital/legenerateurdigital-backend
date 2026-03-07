from openai import OpenAI
from datetime import datetime

client = OpenAI()

async def generate_social_text(reseau: str, format: str, objectif: str, ton: str, langue: str, prompt: str):
    """
    Générateur IA officiel LGD pour posts réseaux sociaux.
    Ultra optimisé pour produire un contenu professionnel + hashtags.
    """

    full_prompt = f"""
Tu es un expert en copywriting marketing digital.
Génère un post optimisé pour le réseau : {reseau}
Format : {format}
Objectif : {objectif}
Ton : {ton}
Langue : {langue}

CONTEXTE UTILISATEUR :
{prompt}

Structure attendue :
1. Titre court percutant
2. Texte principal structuré
3. Liste de hashtags pertinents en fin (seulement les hashtags, pas de #Hashtags:)

Réponds uniquement sous forme JSON :
{{
 "titre": "...",
 "contenu": "...",
 "hashtags": ["...", "..."]
}}
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Tu es un expert marketing spécialisé en contenu social media."},
            {"role": "user", "content": full_prompt},
        ],
        max_tokens=600,
        temperature=0.9
    )

    raw = completion.choices[0].message.content

    import json
    try:
        data = json.loads(raw)
        return {
            "titre": data.get("titre", "Post IA"),
            "contenu": data.get("contenu", ""),
            "hashtags": data.get("hashtags", []),
        }
    except:
        # fallback minimal
        return {
            "titre": "Post IA",
            "contenu": raw,
            "hashtags": [],
        }
