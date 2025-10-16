# main.py
from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlalchemy import text
from sqlmodel import SQLModel, Field, Session, select, create_engine

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
def _split_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

CORS_ORIGINS = _split_env_list(os.getenv("CORS_ORIGINS")) or [
    "http://localhost:3000",
]

ALLOWED_METHODS = _split_env_list(os.getenv("ALLOWED_METHODS")) or ["*"]
ALLOWED_HEADERS = _split_env_list(os.getenv("ALLOWED_HEADERS")) or ["*"]

app = FastAPI(
    title="LegenerateurDigital API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
)

# -----------------------------------------------------------------------------
# Database (PostgreSQL on Render with SSL + retries)
# -----------------------------------------------------------------------------
RAW_DB_URL = (os.getenv("DATABASE_URL") or "sqlite:///database.db").strip()

def _normalize_pg_url(url: str) -> str:
    # force psycopg2 driver for SQLAlchemy
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

ENGINE_KW = {"pool_pre_ping": True, "pool_recycle": 1800}

if RAW_DB_URL.startswith("postgresql"):
    DB_URL = _normalize_pg_url(RAW_DB_URL)
    engine = create_engine(DB_URL, connect_args={"sslmode": "require"}, **ENGINE_KW)
else:
    engine = create_engine(RAW_DB_URL, **ENGINE_KW)

def init_db_with_retry(max_attempts: int = 12, delay_sec: int = 5) -> bool:
    """
    Ping la DB et crée les tables. N'échoue pas l'app si la DB est lente à démarrer.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.begin() as conn:
                conn.execute(text("SELECT 1"))
                SQLModel.metadata.create_all(bind=conn)
            logger.info("✅ Database ready (attempt %s/%s).", attempt, max_attempts)
            return True
        except Exception as e:
            logger.warning("DB not ready (attempt %s/%s): %s", attempt, max_attempts, e)
            time.sleep(delay_sec)
    logger.error("⚠️ DB still not reachable after %s attempts. Continuing without failing.", max_attempts)
    return False

@app.on_event("startup")
def on_startup():
    init_db_with_retry()

# -----------------------------------------------------------------------------
# Auth (JWT)
# -----------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Ne pas faire planter le déploiement si la variable manque : générer une clé éphémère
    JWT_SECRET = os.urandom(48).hex()
    logger.warning("JWT_SECRET is missing in environment. Using a temporary in-memory key.")

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

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# DB session dep
# -----------------------------------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
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

# -----------------------------------------------------------------------------
# Routes de base & santé
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "LegenerateurDigital API"}

# Health checks SANS accès DB (pour Render)
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Auth API minimale
# -----------------------------------------------------------------------------
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
