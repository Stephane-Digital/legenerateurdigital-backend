FROM python:3.11-slim

# Empêche la génération de fichiers pyc et force le flush du log
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copier et installer les dépendances
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le projet
COPY . /app

# Exposer le port utilisé par Render
EXPOSE 8000

# Lancer l'application avec uvicorn (Render fournit automatiquement $PORT)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
