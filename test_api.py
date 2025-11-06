import requests

try:
    r = requests.get("http://127.0.0.1:8000/")
    print("✅ Réponse du backend :", r.status_code, r.text)
except Exception as e:
    print("❌ Erreur :", e)
