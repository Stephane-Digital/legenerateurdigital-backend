# main.py
from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import Optional, Iterable, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import text

# -----------------------------------------------------------------------------
# Config & CORS
# -----------------------------------------------------------------------------
def _split_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

CORS_ORIGINS = _split_env_list(os.getenv("CORS_ORIGINS")) or [
    "http://localhost:3000",
    "https://legeneratedigital-front.vercel.app",
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
# Database (PostgreSQL on Render with SSL)
# -----------------------------------------------------------------------------
RAW_DB_URL = os.getenv("DATABASE_URL", "sqlite:///database.db").strip()

# Force driver + SSL for Render Postgres
def _normalize_pg_url(url: str) -> str:
    # ensure psycopg2 driver in URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

ENGINE_KW = {
    # Render free tier can sleep; keep the pool healthy
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if RAW_DB_URL.startswith("postgresql"):
    DB_URL = _normalize_pg_url(RAW_DB_URL)
    engine = create_engine(DB_URL, connect_args={"sslmode": "require"}, **ENGINE_KW)
else:
    # SQLite or other
    engine = create_engine(RAW_DB_URL, **ENGINE_KW)

def get_session():
    with Session(engine) as session:
        yield session

# -----------------------------------------------------------------------------
# Auth (JWT)
# -----------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is missing. Set it in Render > Environment (a long random string)."
    )

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
# Dependencies
# -----------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise credentials_exception
    return user

# -----------------------------------------------------------------------------
# Startup: create tables
# -----------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# -----------------------------------------------------------------------------
# Routes: base & health
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "LegenerateurDigital API"}

@app.get("/healthz")
def healthz():
    # App health + DB ping
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "up"}
    except Exception:
        return {"status": "ok", "db": "down"}

# -----------------------------------------------------------------------------
# Auth routes
# -----------------------------------------------------------------------------
@app.post("/auth/register", response_model=Token, status_code=201)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    # Check email uniqueness
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
