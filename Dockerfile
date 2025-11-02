# --- Étape 1 : base Python ---
FROM python:3.11-slim

# Empêcher la création de fichiers .pyc et forcer les logs à s'afficher immédiatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Créer le dossier de travail
WORKDIR /app

# Copier les dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le reste du code
COPY . .

# Exposer le port (Render utilisera automatiquement la variable $PORT)
EXPOSE 8000

# Lancer l'application FastAPI
CMD ["sh", "-c", "echo '🚀 Lancement du backend sur le port ${PORT:-8000}...' && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
