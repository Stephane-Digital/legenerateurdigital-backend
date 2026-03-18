import os
import importlib
from dotenv import load_dotenv

# ==========================================================
# 💎 UTILITAIRE — Rechargement sécurisé de la configuration
# ==========================================================

def reload_env(target_dir: str = None):
    """
    Recharge le fichier .env et met à jour les variables d'environnement
    sans redémarrer le serveur.
    """
    env_path = os.path.join(target_dir or os.getcwd(), ".env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Fichier .env introuvable : {env_path}")

    load_dotenv(env_path, override=True)
    return f"✅ Variables d'environnement rechargées depuis : {env_path}"


def reload_modules(modules: list[str]):
    """
    Recharge dynamiquement certains modules Python critiques (auth, db, etc.)
    """
    reloaded = []
    for module_name in modules:
        try:
            if module_name in globals():
                importlib.reload(globals()[module_name])
            else:
                importlib.import_module(module_name)
            reloaded.append(module_name)
        except Exception as e:
            reloaded.append(f"⚠️ Erreur sur {module_name} : {e}")
    return reloaded
