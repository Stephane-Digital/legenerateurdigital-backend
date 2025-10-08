FROM python:3.11-slim

WORKDIR /app
COPY . .

# Installer les dépendances nécessaires
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

# Ouvrir le port utilisé par le serveur
EXPOSE 8000

# Lancer l'application en écoutant le port défini par Render
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
