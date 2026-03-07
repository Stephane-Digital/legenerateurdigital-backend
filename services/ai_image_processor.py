import io
from PIL import Image, ImageEnhance, ImageFilter
import base64

# Ratios LGD officiels
RATIOS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

def load_image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")

def apply_filter(img: Image.Image, filter_name: str):
    if filter_name == "cinematic":
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.4)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    elif filter_name == "neon":
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(2.2)
    elif filter_name == "gold":
        r, g, b = img.split()
        r = r.point(lambda i: i * 1.3)
        g = g.point(lambda i: i * 1.1)
        img = Image.merge("RGB", (r, g, b))
    return img

def resize_to_ratio(img: Image.Image, ratio: str):
    target_w, target_h = RATIOS.get(ratio, RATIOS["1:1"])
    return img.resize((target_w, target_h), Image.LANCZOS)

def image_to_base64(img: Image.Image):
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def process_image(data: bytes, ratio="1:1", filter_name=None):
    img = load_image_from_bytes(data)

    if filter_name:
        img = apply_filter(img, filter_name)

    img = resize_to_ratio(img, ratio)
    return image_to_base64(img)
