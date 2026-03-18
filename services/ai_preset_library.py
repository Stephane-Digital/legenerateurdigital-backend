import base64
import os

PRESETS_DIR = "assets/presets"

def load_preset(name: str):
    path = os.path.join(PRESETS_DIR, f"{name}.png")

    if not os.path.exists(path):
        raise FileNotFoundError("Preset introuvable")

    with open(path, "rb") as f:
        data = f.read()

    return base64.b64encode(data).decode("utf-8")

def list_presets():
    return [
        f.replace(".png", "")
        for f in os.listdir(PRESETS_DIR)
        if f.endswith(".png")
    ]
