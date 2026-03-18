import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Charge config Alembic
config = context.config

# Active loggers
fileConfig(config.config_file_name)

# Ajoute le répertoire backend au PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, BACKEND_DIR)

# Import Base SQLAlchemy
from database import Base

# IMPORTS RÉELS EXISTANTS DANS TON BACKEND (IMPORTANT)
import models.user_model
import models.automation_model
import models.campaign_model
import models.library_item_model     # <-- CORRECT
import models.sales_page_model
import models.guide_model
import models.content_history_model
import models.social_post_model

# Utilisé pour autogenerate
target_metadata = Base.metadata


# ==========================
# Mode Offline
# ==========================
def run_migrations_offline():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL manquant dans l'environnement !")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ==========================
# Mode Online
# ==========================
def run_migrations_online():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL n'est pas défini !")

    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
