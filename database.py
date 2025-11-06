# =============================================================
# 🗄️ DATABASE — Configuration SQLModel (LGD)
# =============================================================
from sqlmodel import SQLModel, create_engine
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Lire la variable DATABASE_URL depuis .env ou Render
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

# Création du moteur
engine = create_engine(DATABASE_URL, echo=False)

# Fonction d'initialisation des tables
def init_db():
    SQLModel.metadata.create_all(engine)
