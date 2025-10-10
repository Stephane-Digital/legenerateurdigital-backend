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
