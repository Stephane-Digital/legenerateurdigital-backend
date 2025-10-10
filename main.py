import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Récup CORS depuis les variables Render
origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
]

allowed_headers = [
    h.strip()
    for h in os.getenv("ALLOWED_HEADERS", "Content-Type,Authorization").split(",")
    if h.strip()
]

allowed_methods = [
    m.strip()
    for m in os.getenv("ALLOWED_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS").split(",")
    if m.strip()
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],     # pour debug : tu peux mettre ["*"], mais mieux vaut lister tes domaines Vercel
    allow_credentials=True,
    allow_methods=allowed_methods or ["*"],
    allow_headers=allowed_headers or ["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ping")
def ping():
    return {"pong": True}

# Permet de lancer localement, et Render lancera via uvicorn (voir Dockerfile)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time

app = FastAPI()

origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterPayload(BaseModel):
    email: str
    password: str

class LoginPayload(BaseModel):
    email: str
    password: str

fake_db = {}

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time())}

@app.post("/auth/register")
def register(p: RegisterPayload):
    if p.email in fake_db:
        raise HTTPException(400, "Email déjà utilisé.")
    fake_db[p.email] = {"password": p.password}
    return {"ok": True}

@app.post("/auth/login")
def login(p: LoginPayload):
    user = fake_db.get(p.email)
    if not user or user["password"] != p.password:
        raise HTTPException(401, "Identifiants invalides.")
    # simple token demo
    return {"token": f"demo-{p.email}"}

@app.get("/profile")
def profile(token: str):
    # démo : token = "demo-email"
    if not token.startswith("demo-"):
        raise HTTPException(401, "Non authentifié.")
    email = token.replace("demo-", "", 1)
    return {"email": email}
