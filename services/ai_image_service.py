import base64
import io
from PIL import Image
from openai import OpenAI

client = OpenAI()

def generate_image(prompt: str, ratio: str = "square"):
    size = {
        "square": "1024x1024",
        "portrait": "1024x1536",
        "landscape": "1536x1024"
    }[ratio]

    res = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size
    )

    img_b64 = res.data[0].b64_json
    return img_b64
