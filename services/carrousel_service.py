from sqlalchemy.orm import Session
from models.carrousel_model import Carrousel
from models.carrousel_slide_model import CarrouselSlide


# ============================================================
# 🟦 CRÉATION DU CARROUSEL
# ============================================================
def create_carrousel(db: Session, user_id: int, title: str, description: str = ""):
    car = Carrousel(
        user_id=user_id,
        title=title,
        description=description,
    )
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


# ============================================================
# 🟦 MISE À JOUR DU CARROUSEL (Titre / Desc)
# ============================================================
def update_carrousel(db: Session, carrousel: Carrousel, title: str, description: str):
    carrousel.title = title
    carrousel.description = description
    db.commit()
    db.refresh(carrousel)
    return carrousel


# ============================================================
# 🟦 REMPLACER LES SLIDES (JSON Layers)
# ============================================================
def set_carrousel_slides(db: Session, carrousel_id: int, slides: list):
    # Supprimer anciens slides
    db.query(CarrouselSlide).filter(CarrouselSlide.carrousel_id == carrousel_id).delete()
    db.commit()

    # Ajouter les slides
    for index, slide in enumerate(slides):
        new_slide = CarrouselSlide(
            carrousel_id=carrousel_id,
            position=index,
            title=slide.get("title", ""),
            json_layers=slide.get("json_layers", "[]"),
        )
        db.add(new_slide)

    db.commit()

    return db.query(CarrouselSlide).filter(CarrouselSlide.carrousel_id == carrousel_id).all()
