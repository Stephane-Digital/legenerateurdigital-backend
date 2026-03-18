Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Initialisation du backend LGD..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ================================
# 🟦 Activation venv
# ================================
Write-Host "Activation de l'environnement virtuel..." -ForegroundColor Yellow

$venvPath = ".\.venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    & $venvPath
} else {
    Write-Host "❌ Environnement virtuel introuvable (.venv)" -ForegroundColor Red
    exit
}

# ================================
# 🟦 Vérification du port 8000
# ================================
Write-Host "Vérification des processus Uvicorn sur le port 8000..." -ForegroundColor Yellow

$process = netstat -ano | Select-String ":8000"

if ($process) {
    Write-Host "⚠️ Uvicorn détecté sur le port 8000 → arrêt..." -ForegroundColor Yellow
    $pid = ($process -split "\s+")[-1]
    taskkill /PID $pid /F
    Start-Sleep -Seconds 1
} else {
    Write-Host "Aucun processus Uvicorn trouvé sur le port 8000." -ForegroundColor Green
}

# ================================
# 🟦 Vérification fichier .env
# ================================
if (Test-Path ".env") {
    Write-Host "Fichier .env détecté et prêt." -ForegroundColor Green
} else {
    Write-Host "❌ Aucun fichier .env trouvé à la racine du backend !" -ForegroundColor Red
    exit
}

# ================================
# 🚀 Démarrage backend
# ================================
Write-Host "Démarrage du backend LGD sur http://127.0.0.1:8000 ..." -ForegroundColor Magenta

uvicorn main:app --reload --host 0.0.0.0 --port 8000
