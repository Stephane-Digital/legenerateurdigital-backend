# ============================================================
# 💎 LE GÉNÉRATEUR DIGITAL - BACKEND (FASTAPI + PRISMA)
# ============================================================

# --- Étape 1 : Base Python stable ---
FROM python:3.11-slim

# --- Étape 2 : Environnement propre ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Étape 3 : Dépendances système nécessaires ---
# Ajout de libatomic1 (nécessaire pour Prisma CLI Node.js)
# + build-essential pour compiler proprement certains paquets
RUN apt-get update && apt-get install -y \
    libatomic1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Étape 4 : Répertoire de travail ---
WORKDIR /app

# --- Étape 5 : Copier les dépendances Python ---
COPY requirements.txt .

# --- Étape 6 : Installation silencieuse et fiable des libs Python ---
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Étape 7 : Copier le reste du projet ---
COPY . .

# --- Étape 8 : Exposer le port (Render détecte automatiquement $PORT) ---
EXPOSE 8000

# --- Étape 9 : Commande de démarrage ---
# Log clair au lancement + support du port Render dynamique
CMD ["sh", "-c", "echo '🚀 Lancement du backend LGD sur le port ${PORT:-8000}...' && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
