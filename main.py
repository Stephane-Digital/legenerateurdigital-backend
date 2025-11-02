from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlmodel import SQLModel, Field, Session, select, create_engine
from sqlalchemy import text

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List

# ----------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)

# ----------------------------------------------------------------------
# FASTAPI INITIALISATION
# ----------------------------------------------------------------------
app = FastAPI(
    title="LeGenerateurDigital API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ----------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------
extra_origins = os.getenv("CORS_ORIGINS", "")
extra = [o.strip() for o in extra_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",  # autoriser toutes les URLs *.vercel.app
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        *extra,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# DATABASE CONFIGURATION (PostgreSQL Render)
# ----------------------------------------------------------------------
RAW_DB_URL = (os.getenv("DATABASE_URL") or "sqlite:///database.db").strip()


def _normalize_pg_url(url: str) -> str:
    """Normalise la chaîne PostgreSQL pour SQLAlchemy."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


ENGINE_KW = {"pool_pre_ping": True, "pool_recycle": 1800}

if "postgres" in RAW_DB_URL:
    DB_URL = _normalize_pg_url(RAW_DB_URL)
    engine = create_engine(DB_URL, connect_args={"sslmode": "require"}, **ENGINE_KW)
else:
    engine = create_engine(RAW_DB_URL, **ENGINE_KW)

# ----------------------------------------------------------------------
# INIT DB + TABLES
# ----------------------------------------------------------------------
def init_db_with_retry(max_attempts: int = 12, delay_sec: int = 5) -> bool:
    """Essaye plusieurs fois de se connecter à la DB, puis crée les tables."""
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database reachable (attempt %s/%s).", attempt, max_attempts)

            # ✅ Création des tables ici
            SQLModel.metadata.create_all(bind=engine)
            logger.info("✅ Tables created or already exist.")
            return True

        except Exception as e:
            logger.warning("⚠️ Database not ready (attempt %s/%s): %s", attempt, max_attempts, e)
            time.sleep(delay_sec)

    logger.error("❌ Could not connect to database after %s attempts.", max_attempts)
    return False


@app.on_event("startup")
def startup_event():
    """Démarrage de l’app - attend que la DB soit prête avant de continuer"""
    if init_db_with_retry():
        logger.info("🚀 Application started and database initialized.")
    else:
        logger.error("❌ Failed to initialize database.")


# ----------------------------------------------------------------------
# TEST CONNEXION DB
# ----------------------------------------------------------------------
@app.get("/db-test")
def test_db_connection():
    """Test la connexion à la base PostgreSQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NOW()")).fetchone()
            return {"ok": True, "message": "Connexion OK ✅", "server_time": str(result[0])}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ----------------------------------------------------------------------
# DEBUG TABLES (optionnel)
# ----------------------------------------------------------------------
@app.get("/debug/db-tables")
def debug_db_tables():
    """Permet de vérifier si les tables existent."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            ))
            tables = [row[0] for row in result]
        return {"tables": tables}
    except Exception as e:
        return {"error": str(e)}


# ----------------------------------------------------------------------
# AUTHENTIFICATION (JWT)
# ----------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = os.urandom(48).hex()
    logger.warning("⚠️ JWT_SECRET missing — using temporary key.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])


# ----------------------------------------------------------------------
# MODELES SQLMODEL
# ----------------------------------------------------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    email: str
    password: str
    full_name: Optional[str] = None


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# ----------------------------------------------------------------------
# DB SESSION & AUTH HELPERS
# ----------------------------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        if not email:
            raise cred_exc
    except JWTError:
        raise cred_exc

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise cred_exc
    return user


# ----------------------------------------------------------------------
# ROUTES PRINCIPALES
# ----------------------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "LeGenerateurDigital API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ----------------------------------------------------------------------
# ROUTES AUTH
# ----------------------------------------------------------------------
@app.post("/auth/register", response_model=Token, status_code=201)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token({"sub": user.email})
    return Token(access_token=token)


@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token({"sub": user.email})
    return Token(access_token=token)


@app.get("/users/me", response_model=User)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/debug/db-drop")
def debug_db_drop():
    """Supprime toutes les tables (⚠️ irréversible)"""
    try:
        SQLModel.metadata.drop_all(bind=engine)
        return {"ok": True, "message": "All tables dropped."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
