# ===============================================================
# 🧰 Script de réparation — bcrypt & passlib (Le Générateur Digital)
# ===============================================================
# Auteur : Stéphane & GPT-5
# Objectif : Corriger les conflits bcrypt/passlib et vérifier le hash

Write-Host "`n🧩 Réparation du module bcrypt/passlib en cours..." -ForegroundColor Cyan

# Étape 1 : Désactivation de l'environnement virtuel si actif
if (Test-Path .\.venv\Scripts\deactivate.ps1) {
    Write-Host "🔌 Désactivation du venv (si actif)..." -ForegroundColor DarkGray
    deactivate 2>$null
}

# Étape 2 : Nettoyage des anciennes versions globales
Write-Host "🧹 Suppression des anciennes installations globales..." -ForegroundColor DarkGray
pip uninstall bcrypt -y 2>$null
pip uninstall passlib -y 2>$null

# Étape 3 : Activation du venv
Write-Host "⚙️ Activation de l'environnement virtuel..." -ForegroundColor DarkGray
& .\.venv\Scripts\Activate.ps1

# Étape 4 : Réinstallation propre des versions stables
Write-Host "📦 Réinstallation des dépendances locales..." -ForegroundColor Yellow
pip install --force-reinstall "bcrypt==4.0.1" "passlib[bcrypt]==1.7.4"

# Étape 5 : Vérification du chemin de bcrypt
Write-Host "`n🔎 Vérification du chemin de bcrypt..." -ForegroundColor Cyan
python -m pip show bcrypt

# Étape 6 : Test de hachage automatique
Write-Host "`n🧪 Test de hachage SHA256 + bcrypt..." -ForegroundColor Cyan
python - << 'PYCODE'
from passlib.context import CryptContext
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password = "123456"
sha_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
hashed = pwd_context.hash(sha_hash)

print(f"SHA256: {sha_hash}")
print(f"✅ bcrypt OK: {hashed}")
PYCODE

Write-Host "`n🎉 Test terminé ! Si le hash s'affiche correctement, tout est réparé." -ForegroundColor Green
Write-Host "➡️ Tu peux relancer ton backend avec : .\run_local.ps1" -ForegroundColor Yellow
