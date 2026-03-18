# =============================================================
# 💎 LE GÉNÉRATEUR DIGITAL — LOGGER PREMIUM
# =============================================================
import logging
import os
from datetime import datetime
from colorama import Fore, Style

# 📁 Dossier de logs
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 🕓 Fichier journal du jour
LOG_FILE = os.path.join(LOG_DIR, f"lgd_{datetime.now().strftime('%Y-%m-%d')}.log")

# 📋 Configuration du logger principal
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] 💎 LGD | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("LGD")

def info(message: str):
    print(f"{Fore.YELLOW}💎 {Style.RESET_ALL}{message}")
    logger.info(message)

def success(message: str):
    print(f"{Fore.GREEN}✅ {Style.RESET_ALL}{message}")
    logger.info(message)

def warning(message: str):
    print(f"{Fore.LIGHTRED_EX}⚠️ {Style.RESET_ALL}{message}")
    logger.warning(message)

def error(message: str):
    print(f"{Fore.RED}🛑 {Style.RESET_ALL}{message}")
    logger.error(message)
