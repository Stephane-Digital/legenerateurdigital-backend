import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Charger variables .env
load_dotenv()

# ==============================
# 🔐 Chargement sécurisé .env
# ==============================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "lgd-files")

if not SUPABASE_URL:
    raise Exception("❌ SUPABASE_URL absente du .env")

if not SUPABASE_KEY:
    raise Exception("❌ SUPABASE_KEY absente du .env")

# ==============================
# 🔥 Client Supabase
# ==============================
client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# =====================================================
# 📤 Upload image (images + carrousels + librairie)
# =====================================================
def upload_image(file, folder: str):
    """Upload image dans le bucket Supabase"""

    extension = file.filename.split(".")[-1].lower()
    filename = f"{folder}/{os.urandom(16).hex()}.{extension}"

    file_bytes = file.file.read()

    response = client.storage.from_(SUPABASE_BUCKET).upload(
        path=filename,
        file=file_bytes,
        file_options={"content-type": file.content_type},
    )

    if response is None:
        raise Exception("❌ Erreur upload Supabase")

    # URL publique
    public_url = client.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
    return public_url


# =====================================================
# ❌ Suppression fichier
# =====================================================
def delete_file(file_url: str):
    """Supprime un fichier du bucket Supabase"""
    try:
        # Extraire le chemin réel dans le bucket
        path = file_url.split(f"/storage/v1/object/public/{SUPABASE_BUCKET}/")[-1]
        client.storage.from_(SUPABASE_BUCKET).remove(path)
    except Exception as e:
        print("⚠️ Erreur suppression Supabase :", e)
