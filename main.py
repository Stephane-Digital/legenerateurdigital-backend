from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select

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

# --- Base de données SQLite ---
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, echo=False)

# --- Modèle User ---
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str
    password: str

# --- Création automatique de la table ---
SQLModel.metadata.create_all(engine)

@app.get("/")
def root():
    return {"status": "ok", "message": "API opérationnelle"}

# ✅ Inscription
@app.post("/auth/register")
async def register(request: Request):
    data = await request.json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    with Session(engine) as session:
        existing_user = session.exec(select(User).where(User.email == email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Utilisateur déjà existant")

        user = User(name=name, email=email, password=password)
        session.add(user)
        session.commit()
        session.refresh(user)

    return {"message": "Compte créé avec succès 🎉", "user": {"email": email, "name": name}}

# ✅ Connexion
@app.post("/auth/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or user.password != password:
            raise HTTPException(status_code=401, detail="Identifiants invalides")

    return {"access_token": "fake-jwt-token-123456", "user": {"email": email, "name": user.name}}

# Exemple route test
@app.get("/dashboard")
def dashboard():
    return {"message": "Bienvenue sur ton tableau de bord 🔒"}
from fastapi import FastAPI

app = FastAPI()

# ... ici tes autres routes existantes (login, register, etc.)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
