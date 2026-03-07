from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import URL

from config.settings import settings

# ============================================================
# LGD — SQLAlchemy Base / Engine / Session
# ============================================================

Base = declarative_base()


def _build_db_url() -> URL | str:
    """
    Build a safe SQLAlchemy URL object from the DATABASE_URL string.
    This avoids Windows/encoding edge-cases where a raw string DSN
    may contain stray non-utf8 bytes or be decoded differently.
    """
    raw = settings.DATABASE_URL

    if isinstance(raw, URL):
        return raw

    try:
        return URL.create(raw.split("://", 1)[0], query={})
    except Exception:
        return raw


def _create_engine():
    raw = settings.DATABASE_URL

    return create_engine(
        raw,
        pool_pre_ping=True,
        future=True,
        connect_args={
            "client_encoding": "UTF8",
        },
    )


engine = _create_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
