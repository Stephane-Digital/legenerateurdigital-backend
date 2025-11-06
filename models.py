# =============================================================
# 🧱 MODELS — Schémas de données SQLModel (LGD)
# =============================================================

from sqlmodel import SQLModel, Field
from typing import Optional

# -------------------------------------------------------------
# 📘 Modèle Bibliothèque
# -------------------------------------------------------------
class Bibliotheque(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    userId: int
    titre: str
    categorie: str
    contenu: str
