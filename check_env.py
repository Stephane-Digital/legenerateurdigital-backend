"""
==============================================================
🧠 LE GÉNÉRATEUR DIGITAL — CHECK_ENV.PY
==============================================================
Script de vérification automatique des variables d’environnement
avant le lancement du backend FastAPI.
---------------------------------------------------------------
✅ Vérifie :
    - Clés essentielles (.env)
    - Chemins de stockage
    - Mode local ou Render
    - Connexion DB et clé OpenAI
---------------------------------------------------------------
"""

import os
from dotenv import load_dotenv
from colorama import Fore, Style, init

# =============================================================
# 🧹 AUTO-CORRECTION DU FICHIER .env (UTF-8 sans BOM)
# =============================================================
import io

def fix_env_encoding(file_path=".env"):
    """Supprime le BOM et normalise le format du fichier .env en UTF-8 propre."""
    if not os.path.exists(file_path):
        return

    try:
        # Lire le contenu brut pour détecter le BOM ou caractères indésirables
        with open(file_path, "rb") as f:
            raw = f.read()

        # Supprime BOM s'il existe (EF BB BF)
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]

        # Nettoie les caractères invisibles éventuels
        cleaned = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        # Réécrit proprement
        with io.open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(cleaned.decode("utf-8", errors="ignore"))

        print("🧹 Fichier .env corrigé et encodé en UTF-8 propre.")
    except Exception as e:
        print(f"⚠️ Impossible de corriger .env : {e}")

# Exécute la correction dès le chargement
fix_env_encoding(".env")

# Initialisation des couleurs pour le terminal
init(autoreset=True)

# Chargement du fichier .env
load_dotenv()

# =============================================================
# 🧩 VARIABLES ESSENTIELLES À CONTRÔLER
# =============================================================
REQUIRED_VARS = [
    "APP_ENV",
    "DATABASE_URL",
    "JWT_SECRET",
    "CORS_ORIGINS",
    "BACKEND_URL",
    "FRONTEND_URL"
]

AI_VARS = ["OPENAI_API_KEY", "OPENAI_PROJECT_ID"]

# =============================================================
# ⚙️ DÉTECTION AUTOMATIQUE DU CONTEXTE
# =============================================================
env = os.getenv("APP_ENV", "undefined").lower()
is_render = "onrender.com" in os.getenv("BACKEND_URL", "")
is_local = env in ["dev", "development", "local"]

# =============================================================
# 🔍 FONCTIONS DE CONTRÔLE
# =============================================================
def check_var(var_name):
    value = os.getenv(var_name)
    if not value or "xxxxx" in value.lower() or value.strip() == "":
        print(f"{Fore.RED}❌ Manquante : {var_name}")
        return False
    print(f"{Fore.GREEN}✅ OK : {var_name}")
    return True


def check_env():
    print(f"\n{Fore.YELLOW}🚀 Vérification de l’environnement LGD...\n")

    missing = False

    print(f"{Fore.CYAN}--- Variables principales ---")
    for var in REQUIRED_VARS:
        if not check_var(var):
            missing = True

    print(f"\n{Fore.CYAN}--- Variables IA / OpenAI ---")
    for var in AI_VARS:
        if not check_var(var):
            missing = True

    print(f"\n{Fore.CYAN}--- Détails du contexte ---")
    print(f"{Fore.MAGENTA}• Mode : {env}")
    print(f"{Fore.MAGENTA}• Contexte Render : {'✅ Oui' if is_render else '❌ Non'}")
    print(f"{Fore.MAGENTA}• Contexte Local : {'✅ Oui' if is_local else '❌ Non'}")

    if not missing:
        print(f"\n{Fore.GREEN}🎯 Environnement complet — tout est prêt pour le lancement 🚀\n")
    else:
        print(f"\n{Fore.RED}⚠️ Des variables manquent ou sont invalides ! Corrige le fichier .env avant de démarrer FastAPI.\n")

# =============================================================
# 🧠 LANCEMENT
# =============================================================
if __name__ == "__main__":
    check_env()
