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

# Exposer le port (Render utilisera PORT automatiquement)
EXPOSE 8000

# ✅ Lancer directement Uvicorn sans sous-shell
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
