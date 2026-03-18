from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user_model import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Version simplifiée V4 :
    - Récupère le PREMIER utilisateur trouvé en base.
    - Sert de "user courant" pour les modules (Library, Automatisations, etc.).
    - On branchera ça plus tard sur le vrai système d'auth (JWT/cookies).
    """
    user = db.query(User).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Aucun utilisateur trouvé en base. Crée au moins un user dans la table 'users'.",
        )

    return user
