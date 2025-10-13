from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ Autoriser le frontend (Vercel) à appeler l’API Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://legenerateurdigital-front.vercel.app",  # ton front déployé
        "http://localhost:3000",  # utile pour les tests locaux
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Route de test (health check)
@app.get("/")
def root():
    return {"status": "ok", "message": "API opérationnelle"}

# ✅ Route de connexion
@app.post("/auth/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    # Simple logique de démo — tu pourras la remplacer par ta vraie base de données
    if email == "contact@first-digital-academy.com" and password == "123456":
        return {
            "access_token": "fake-jwt-token-123456",
            "token_type": "bearer",
            "user": {"email": email}
        }

    raise HTTPException(status_code=401, detail="Identifiants invalides")

# ✅ Exemple d’une route protégée
@app.get("/dashboard")
def dashboard():
    return {"message": "Bienvenue sur ton tableau de bord 🔒"}
