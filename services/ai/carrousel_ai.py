import openai
import re


def generate_preset_ai(payload: dict):
    # prompt construit côté frontend
    prompt = payload.get("prompt", "")
    slides_count = payload.get("slides_count", 6)

    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Tu génères des carrousels structurés."},
            {"role": "user", "content": f"{prompt}\nNombre de slides : {slides_count}"}
        ],
    )

    text = response.choices[0].message.content
    slides = parse_slides_from_text(text)

    return {
        "title": "Carrousel IA",
        "slides": slides,
    }


def generate_background_ai(payload: dict):
    prompt = payload.get("prompt", "")

    if not prompt:
        return {"background": None}

    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Décris un background simple pour un carrousel."},
            {"role": "user", "content": prompt}
        ],
    )

    text = response.choices[0].message.content
    return {"background": text.strip()}


def generate_from_slides_ai(payload: dict):
    slides = payload.get("slides", [])
    title = payload.get("title", "Carrousel IA")

    enriched = []
    for s in slides:
        enriched.append({
            "title": s.get("title"),
            "json_layers": s.get("json_layers", "[]")
        })

    return {
        "title": title,
        "slides": enriched
    }


def parse_slides_from_text(text: str):
    regex = r"\*\*Slide \d+\*\*[:\-]?\s*(.*?)(?=\*\*Slide|\Z)"
    matches = re.findall(regex, text, re.DOTALL)

    slides = []
    for m in matches:
        slides.append({
            "title": "",
            "json_layers": "[]"
        })
    return slides
