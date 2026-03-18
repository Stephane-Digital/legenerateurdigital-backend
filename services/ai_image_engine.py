import base64
import io
from PIL import Image, ImageEnhance, ImageFilter
from typing import Optional


# ============================================================
# 🔥 IA IMAGE ENGINE (compatible OpenAI & Stable Diffusion)
# ============================================================

def load_image_from_base64(b64: str) -> Image.Image:
    decoded = base64.b64decode(b64)
    return Image.open(io.BytesIO(decoded)).convert("RGB")


def image_to_base64(img: Image.Image) -> str:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


# ============================================================
# 🎨 Color Grading IA
# ============================================================

def apply_color_grading(img: Image.Image, preset: str) -> Image.Image:
    if preset == "cinematic":
        img = ImageEnhance.Color(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    elif preset == "gold":
        gold_filter = ImageEnhance.Color(img).enhance(2.2)
        img = Image.blend(img, gold_filter, 0.35)

    elif preset == "neon":
        neon = img.filter(ImageFilter.FIND_EDGES)
        neon = ImageEnhance.Color(neon).enhance(3)
        neon = ImageEnhance.Brightness(neon).enhance(1.5)
        img = Image.blend(img, neon, 0.25)

    elif preset == "pastel":
        img = ImageEnhance.Color(img).enhance(0.7)
        img = ImageEnhance.Brightness(img).enhance(1.1)

    return img


# ============================================================
# 🖼️ Resize intelligent (COVER)
# ============================================================

def smart_resize(img: Image.Image, width: int, height: int) -> Image.Image:
    original_w, original_h = img.size
    scale = max(width / original_w, height / original_h)

    new_w = int(original_w * scale)
    new_h = int(original_h * scale)

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - width) // 2
    top = (new_h - height) // 2
    right = left + width
    bottom = top + height

    return resized.crop((left, top, right, bottom))
