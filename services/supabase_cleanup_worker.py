# services/supabase_cleanup_worker.py

import asyncio
from services.supabase_service import supabase, SUPABASE_BUCKET
from database import SessionLocal
from models.carousel.carousel_slide_model import CarouselSlide


async def supabase_cleanup_loop():
    """
    NETTOYAGE INTELLIGENT — Option B :
    - Supprime les fichiers orphelins Supabase
    - S’exécute toutes les 24h
    """

    print("🟣 Worker Supabase Cleanup démarré… (Option B)")

    while True:
        try:
            db = SessionLocal()

            # Liste les fichiers du bucket
            files = supabase.storage.from_(SUPABASE_BUCKET).list()

            # Liste des images enregistrées en BDD
            slides = db.query(CarouselSlide).all()

            valid_urls = {s.image_url for s in slides}

            for f in files:
                name = f["name"]

                public_url = (
                    f"{supabase.storage.from_(SUPABASE_BUCKET).get_public_url(name)}"
                )

                if public_url not in valid_urls:
                    print(f"🧹 Suppression fichier orphelin : {name}")
                    supabase.storage.from_(SUPABASE_BUCKET).remove([name])

        except Exception as e:
            print("❌ [Cleanup Worker Error] :", e)

        await asyncio.sleep(60 * 60 * 24)
