# Redeploy fix for Render

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import SQLModel, Field, Session, create_engine, select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# --- Initialisation ---
app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://legenerateurdigital-front.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Base de données ---
from sqlalchemy.engine import URL

raw_url = os.getenv("DATABASE_URL", "sqlite:///database.db")

# 🔒 Forcer SSL pour PostgreSQL sur Render
if raw_url.startswith("postgresql"):
    connect_url = URL.create(raw_url)
    engine = create_engine(str(connect_url), connect_args={"sslmode": "require"})
else:
    engine = create_engine(raw_url)

# --- Sécurité JWT ---
SECRET_KEY = "ton_secret_à_changer"  # ⚠️ Change cette clé par une valeur longue et unique
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Modèles ---
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str
    hashed_password: str


class UserCreate(SQLModel):
    name: str
    email: str
    password: str


class Token(SQLModel):
    access_token: str
    token_type: str


# --- Fonctions utilitaires ---
def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(session: Session, email: str):
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


# --- Création de la base ---
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# --- Routes Auth ---
@app.post("/register", response_model=User)
def register(user: UserCreate):
    with Session(engine) as session:
        existing_user = get_user_by_email(session, user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email déjà enregistré")

        hashed_password = get_password_hash(user.password)
        db_user = User(name=user.name, email=user.email, hashed_password=hashed_password)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user


@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = get_user_by_email(session, form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Identifiants invalides")

        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=User)
def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token invalide")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    with Session(engine) as session:
        user = get_user_by_email(session, email)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return user


@app.get("/health")
def health_check():
    return {"status": "ok"}
