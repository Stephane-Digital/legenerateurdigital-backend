import os
from dotenv import load_dotenv

print("🔍 Vérification du fichier .env...")

env_path = os.path.join(os.getcwd(), ".env")

if not os.path.exists(env_path):
    print("❌ Aucun fichier .env trouvé dans le dossier courant.")
    exit(1)

# Lecture brute pour détecter encodage et caractères cachés
with open(env_path, "rb") as f:
    raw = f.read()

# Vérifie l’encodage UTF-8
if raw.startswith(b"\xef\xbb\xbf"):
    print("⚠️  BOM détecté (UTF-8 avec BOM) -> Corrige avec 'Encodage > Convertir en UTF-8 (sans BOM)' dans Notepad++")
else:
    print("✅ Aucun BOM détecté — fichier propre.")

# Vérifie les caractères non imprimables
invalid_bytes = [b for b in raw if b < 9 or (b > 13 and b < 32)]
if invalid_bytes:
    print(f"⚠️  Caractères invisibles détectés : {invalid_bytes[:10]} ...")
else:
    print("✅ Aucun caractère invisible détecté.")

# Test de chargement réel
try:
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print(f"✅ DATABASE_URL détectée : {db_url}")
        if "postgresql://" in db_url and "?sslmode=require" in db_url:
            print("💎 Format de DATABASE_URL valide ✅")
        else:
            print("⚠️ DATABASE_URL partielle ou format suspect.")
    else:
        print("❌ DATABASE_URL absente du .env.")
except Exception as e:
    print("🚨 Erreur lors du chargement du .env :", e)

print("\n🧹 Vérification terminée.")
