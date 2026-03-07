# ================================================
# BACKEND RESTART SCRIPT - LGD
# ================================================

Write-Host "==============================================="
Write-Host "      REDEMARRAGE COMPLET DU BACKEND LGD       "
Write-Host "==============================================="

# 1) CHEMIN DU VENV
$venv = ".venv/Scripts/Activate.ps1"

# 2) KILL PROCESS PYTHON / UVICORN
Write-Host "Verification des processus Python/Uvicorn..."
$existing = Get-Process | Where-Object { $_.ProcessName -like "python*" }

if ($existing) {
    Write-Host "Arret des processus existants..."
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 1
} else {
    Write-Host "Aucun processus existant."
}

# 3) ACTIVER L ENVIRONNEMENT VIRTUEL
if (Test-Path $venv) {
    Write-Host "Activation du venv..."
    & $venv
    Start-Sleep -Seconds 1
} else {
    Write-Host "ERREUR: venv introuvable."
    exit
}

# 4) CHECK .env
if (Test-Path ".env") {
    Write-Host ".env detecte."
} else {
    Write-Host "ERREUR: fichier .env manquant."
    exit
}

# 5) START SERVER
Write-Host "Demarrage du backend LGD sur http://127.0.0.1:8000 ..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
