from openai import OpenAI
from config.settings import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)


SYSTEM_PROMPT = """
Tu es l'expert ultime en génération de leads,
landing pages premium,
copywriting émotionnel,
conversion directe,
funnels Systeme.io.

Tu écris avec sincérité,
émotion,
authenticité,
profondeur,
ressenti humain,
expertise business.

Tu dois produire des textes 10x plus puissants
qu'une IA générique.
"""


def generate_lead_content(goal: str, brief: str, emotional_style: str, business_context: str | None):
    prompt = f"""
OBJECTIF : {goal}

BRIEF :
{brief}

STYLE :
{emotional_style}

CONTEXTE BUSINESS :
{business_context or 'non précisé'}
"""

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
    )

    return response.choices[0].message.content
