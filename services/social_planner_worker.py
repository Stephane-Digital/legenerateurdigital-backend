import time
from sqlalchemy.orm import Session

from database import SessionLocal
from services.social_log_service import create_log


def process_scheduled_posts(db: Session):
    """
    Ici on intégrera plus tard toute la logique du planificateur.
    Pour le moment : simple log pour vérifier le worker.
    """
    create_log(
        db=db,
        user_id=1,               # Placeholder – remplacé plus tard par véritable user_id
        action="worker_tick",
        details="Social Planner tick executed"
    )


def social_planner_loop():
    """
    Boucle infinie du worker Social Planner.
    Appelée au démarrage du backend dans main.py
    """
    while True:
        db = SessionLocal()
        try:
            process_scheduled_posts(db)
        except Exception as e:
            print("❌ ERREUR Social Planner :", str(e))
        finally:
            db.close()

        time.sleep(60)  # tick toutes les 60 secondes
