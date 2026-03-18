import base64
from PIL import Image

GRADIENTS = {
    "gold_sunset": ("#c79f4f", "#f7e8ad"),
    "luxury_black": ("#000000", "#1a1a1a"),
    "neon_blue": ("#00f0ff", "#0040ff"),
}

def generate_gradient(name: str, width=1080, height=1920):
    if name not in GRADIENTS:
        name = "luxury_black"

    start, end = GRADIENTS[name]

    img = Image.new("RGB", (width, height))

    r1, g1, b1 = tuple(int(start[i:i+2], 16) for i in (1, 3, 5))
    r2, g2, b2 = tuple(int(end[i:i+2], 16) for i in (1, 3, 5))

    for y in range(height):
        ratio = y / height
        r = int(r1 * (1 - ratio) + r2 * ratio)
        g = int(g1 * (1 - ratio) + g2 * ratio)
        b = int(b1 * (1 - ratio) + b2 * ratio)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))

    import io
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=95)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
