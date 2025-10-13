# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🧪 TEST : autoriser toutes les origines (temporaire, juste pour voir si ça débloque)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # <— on remettra des domaines précis après le test
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
