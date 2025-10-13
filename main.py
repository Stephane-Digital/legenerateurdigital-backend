from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Middleware CORS
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

# Stockage temporaire des utilisateurs (en mémoire)
users = {
    "contact@first-digital-academy.com": {
        "name": "GenerateurDigital",
        "password": "Steph@020367$",
    }
}

@app.get("/")
def root():
    return {"status": "ok", "message": "API opérationnelle"}

# ✅ Connexion
@app.post("/auth/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    user = users.get(email)
    if user and user["password"] == password:
        return {
            "access_token": "fake-jwt-token-123456",
            "user": {"email": email, "name": user["name"]},
        }

    raise HTTPException(status_code=401, detail="Identifiants invalides")

# ✅ Inscription
@app.post("/auth/register")
async def register(request: Request):
    data = await request.json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if email in users:
        raise HTTPException(status_code=400, detail="Utilisateur déjà existant")

    # Créer un nouvel utilisateur
    users[email] = {"name": name, "password": password}

    return {"message": "Compte créé avec succès", "user": {"email": email, "name": name}}

# Exemple route protégée
@app.get("/dashboard")
def dashboard():
    return {"message": "Bienvenue sur ton tableau de bord 🔒"}
