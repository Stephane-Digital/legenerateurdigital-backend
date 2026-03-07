import base64
from PIL import Image
import io

def auto_resize_for_network(base64_str: str, network: str):
    formats = {
        "instagram": (1080, 1350),
        "facebook": (1200, 630),
        "linkedin": (1200, 1200),
        "tiktok": (1080, 1920),
    }

    target = formats.get(network, (1080,1080))

    img_bytes = base64.b64decode(base64_str)
    img = Image.open(io.BytesIO(img_bytes))

    img = img.resize(target)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)

    return base64.b64encode(buffer.getvalue()).decode()
