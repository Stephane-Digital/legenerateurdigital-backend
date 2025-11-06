# =============================================================
# 📚 ROUTE LIBRARY — Gestion de la bibliothèque personnelle (LGD)
# =============================================================

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from database import engine
from models import Bibliotheque

# -------------------------------------------------------------
# 🧩 INITIALISATION
# -------------------------------------------------------------
router = APIRouter(prefix="/library", tags=["Library"])

# -------------------------------------------------------------
# 📖 RÉCUPÉRATION DE LA BIBLIOTHÈQUE D’UN UTILISATEUR
# -------------------------------------------------------------
@router.get("/{user_id}")
def get_library(user_id: int):
    """
    Récupère tous les éléments de la bibliothèque appartenant à un utilisateur.
    """
    try:
        with Session(engine) as session:
            items = session.exec(
                select(Bibliotheque).where(Bibliotheque.userId == user_id)
            ).all()
            return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération : {e}")

# -------------------------------------------------------------
# ➕ AJOUT D’UN ÉLÉMENT DANS LA BIBLIOTHÈQUE
# -------------------------------------------------------------
@router.post("/")
def add_item(item: Bibliotheque):
    """
    Ajoute un élément (livre, ressource, automation, etc.) dans la bibliothèque.
    """
    try:
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l’ajout : {e}")

# -------------------------------------------------------------
# ❌ SUPPRESSION D’UN ÉLÉMENT PAR ID
# -------------------------------------------------------------
@router.delete("/{item_id}")
def delete_item(item_id: int):
    """
    Supprime un élément spécifique de la bibliothèque via son ID.
    """
    try:
        with Session(engine) as session:
            item = session.get(Bibliotheque, item_id)
            if not item:
                raise HTTPException(status_code=404, detail="Élément non trouvé")

            session.delete(item)
            session.commit()
            return {"message": "✅ Élément supprimé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression : {e}")

