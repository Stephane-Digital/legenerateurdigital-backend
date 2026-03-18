import os
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional, Tuple

TEMP_DIR = "temp_ai_images"
os.makedirs(TEMP_DIR, exist_ok=True)


# ============================================================
# 🔧 Resize selon format réseaux sociaux
# ============================================================
FORMATS = {
    "story_reel": (1080, 1920),
    "post_square": (1080, 1080),
    "post_vertical": (1080, 1350),
    "landscape": (1920, 1080),
}


def resize_to_format(file, format_key: str):
    """Redimensionne l'image selon le format voulu"""
    if format_key not in FORMATS:
        raise ValueError("Format inconnu")

    width, height = FORMATS[format_key]

    img = Image.open(file.file).convert("RGB")
    img = img.resize((width, height))

    filename = f"{uuid.uuid4()}.jpg"
    path = os.path.join(TEMP_DIR, filename)
    img.save(path, "JPEG", quality=92)

    public_url = f"/static/{filename}"  # tu peux adapter selon ton infra

    return path, public_url


# ============================================================
# 🎨 Composition : background + image + texte + filtre
# ============================================================
def compose_layers(
    background: Optional[str],
    image: Optional[str],
    text: Optional[str],
    format: str,
    position: Tuple[int, int],
    filter: Optional[str] = None,
):
    width, height = FORMATS.get(format, (1080, 1080))

    canvas = Image.new("RGB", (width, height), (10, 10, 10))

    # ---- BACKGROUND ----
    if background:
        try:
            bg = Image.open(background).convert("RGB").resize((width, height))
            canvas.paste(bg, (0, 0))
        except:
            pass

    # ---- IMAGE ----
    if image:
        try:
            fg = Image.open(image).convert("RGBA").resize((width, height))
            canvas.paste(fg, (0, 0), fg)
        except:
            pass

    # ---- TEXTE ----
    if text:
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()

        draw.text(position, text, fill="#FFD700", font=font)

    # ---- FILTRE ----
    if filter == "gold":
        canvas = canvas.filter(ImageFilter.SMOOTH_MORE)
    if filter == "cinematic":
        canvas = canvas.filter(ImageFilter.GaussianBlur(1.2))

    # ---- SAVE ----
    filename = f"compose_{uuid.uuid4()}.jpg"
    path = os.path.join(TEMP_DIR, filename)
    canvas.save(path, "JPEG", quality=92)

    return f"/static/{filename}"


# ============================================================
# 💾 Export final (PNG/JPG)
# ============================================================
def save_temp_image(file_path: str):
    return file_path
