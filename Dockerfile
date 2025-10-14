CMD ["sh", "-c", "echo '📁 Contenu du dossier /app :' && ls -la /app && echo '🚀 Lancement de FastAPI...' && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
