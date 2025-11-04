from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from sqlmodel import SQLModel, Field, Session, select, create_engine
from sqlalchemy import text, Column, Text

import os
import time
import logging
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

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
    openapi_url="/openapi.json",
)

# ----------------------------------------------------------------------
# CORS CONFIGURATION
# ----------------------------------------------------------------------
extra_origins = os.getenv("CORS_ORIGINS", "")
extra = [o.strip() for o in extra_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",
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
# DATABASE CONFIGURATION
# ----------------------------------------------------------------------
RAW_DB_URL = (os.getenv("DATABASE_URL") or "sqlite:///database.db").strip()


def _normalize_pg_url(url: str) -> str:
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


def init_db_with_retry(max_attempts: int = 12, delay_sec: int = 5) -> bool:
    """Essaye plusieurs connexions avant de créer les tables."""
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.begin() as conn:
                conn.execute(text("SELECT 1"))
                SQLModel.metadata.create_all(bind=conn)
            logger.info(f"✅ Database ready (attempt {attempt}/{max_attempts}).")
            return True
        except Exception as e:
            logger.warning(f"⚠️ DB not ready (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(delay_sec)
    logger.error(f"❌ Database still unreachable after {max_attempts} attempts.")
    return False


@app.on_event("startup")
def on_startup():
    init_db_with_retry()

# ----------------------------------------------------------------------
# AUTHENTIFICATION (JWT)
# ----------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = os.urandom(48).hex()
    logger.warning("⚠️ JWT_SECRET missing — using temporary key.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ----------------------------------------------------------------------
# PASSWORD HELPERS
# ----------------------------------------------------------------------
def get_password_hash(password: str) -> str:
    """Hache un mot de passe avec troncature stricte à 72 octets (bcrypt natif)."""
    if not password:
        raise ValueError("Password cannot be empty")

    password_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe avec troncature stricte à 72 octets."""
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Erreur vérification bcrypt : {e}")
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

# ----------------------------------------------------------------------
# SQLMODEL MODELS
# ----------------------------------------------------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    email: str
    password: str
    full_name: Optional[str] = None


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# === MODÈLE IDÉE D’ENTREPRISE ===
class IdeeEntreprise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    userId: Optional[int] = Field(default=None, foreign_key="user.id")
    titre: str
    description: str
    marche: str
    promesse: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ----------------------------------------------------------------------
# DB SESSION HELPERS
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
# MAIN ROUTES
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
# AUTH ROUTES
# ----------------------------------------------------------------------
@app.post("/auth/register", response_model=Token, status_code=201)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    try:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = get_password_hash(payload.password)
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hashed,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_access_token({"sub": user.email})
        return Token(access_token=token)

    except Exception as e:
        logger.error(f"❌ Erreur dans /auth/register : {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

# ----------------------------------------------------------------------
# ENTREPRISE ROUTES — CRÉER SON ENTREPRISE
# ----------------------------------------------------------------------
class IdeeEntrepriseCreate(BaseModel):
    titre: str
    description: str
    marche: str
    promesse: str


@app.post("/api/entreprise/idee", response_model=dict)
def create_idee(
    data: IdeeEntrepriseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Crée une idée d’entreprise pour l’utilisateur connecté."""
    try:
        idee = IdeeEntreprise(
            userId=current_user.id,
            titre=data.titre,
            description=data.description,
            marche=data.marche,
            promesse=data.promesse,
        )
        session.add(idee)
        session.commit()
        session.refresh(idee)
        return {"ok": True, "id": idee.id, "message": "Idée enregistrée avec succès ✅"}
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur création idée : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entreprise/idee", response_model=List[dict])
def list_idees(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retourne toutes les idées enregistrées par l’utilisateur."""
    try:
        idees = session.exec(
            select(IdeeEntreprise).where(IdeeEntreprise.userId == current_user.id)
        ).all()
        return [
            {
                "id": i.id,
                "titre": i.titre,
                "description": i.description,
                "marche": i.marche,
                "promesse": i.promesse,
                "created_at": i.created_at,
            }
            for i in idees
        ]
    except Exception as e:
        logger.error(f"❌ Erreur récupération idées : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/entreprise/idee/{idee_id}", response_model=dict)
def delete_idee(
    idee_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Supprime une idée d’entreprise appartenant à l’utilisateur connecté."""
    try:
        idee = session.exec(
            select(IdeeEntreprise)
            .where(IdeeEntreprise.id == idee_id)
            .where(IdeeEntreprise.userId == current_user.id)
        ).first()

        if not idee:
            raise HTTPException(status_code=404, detail="Idée introuvable ou non autorisée")

        session.delete(idee)
        session.commit()
        return {"ok": True, "message": "Idée supprimée avec succès 🗑️"}

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur suppression idée : {e}")
        raise HTTPException(status_code=500, detail=str(e))
