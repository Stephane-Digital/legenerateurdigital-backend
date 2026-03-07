# =============================================================
# LE GENERATEUR DIGITAL — BACKEND HEALTH CHECK (SAFE VERSION)
# =============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "=============================================================" -ForegroundColor DarkYellow
Write-Host "  LE GENERATEUR DIGITAL - Diagnostic Backend Deluxe" -ForegroundColor Yellow
Write-Host "=============================================================" -ForegroundColor DarkYellow
Write-Host ""

# 1️⃣ Vérification du fichier .env
$envPath = ".\.env"
if (Test-Path $envPath) {
    Write-Host "[OK] Fichier .env détecté à : $envPath" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Fichier .env introuvable à la racine du backend !" -ForegroundColor Red
    exit
}

# 2️⃣ Vérification de DATABASE_URL
$databaseUrl = Get-Content $envPath | Select-String "^DATABASE_URL"
if ($databaseUrl) {
    Write-Host "[OK] DATABASE_URL trouvée :" -NoNewline
    Write-Host " $($databaseUrl -replace 'DATABASE_URL=', '')" -ForegroundColor Cyan
} else {
    Write-Host "[ERREUR] Variable DATABASE_URL absente du .env" -ForegroundColor Red
}

# 3️⃣ Test de connexion PostgreSQL
Write-Host ""
Write-Host "Test de connexion à la base PostgreSQL Render..." -ForegroundColor Yellow
try {
    python -c "import psycopg2, os; from dotenv import load_dotenv; load_dotenv(); conn = psycopg2.connect(os.getenv('DATABASE_URL')); print('[OK] Connexion PostgreSQL réussie'); conn.close()"
} catch {
    Write-Host "[ERREUR] Connexion à la base PostgreSQL échouée !" -ForegroundColor Red
}

# 4️⃣ Test des routes principales
$urls = @(
    @{ name = "Root API"; url = "http://127.0.0.1:8000/" },
    @{ name = "Auth Test"; url = "http://127.0.0.1:8000/auth/test" },
    @{ name = "Reload Check"; url = "http://127.0.0.1:8000/admin/reload/check" }
)

Write-Host ""
Write-Host "Test des routes principales..." -ForegroundColor Yellow
foreach ($test in $urls) {
    try {
        $res = Invoke-WebRequest -Uri $test.url -UseBasicParsing -TimeoutSec 5
        if ($res.StatusCode -eq 200) {
            Write-Host "[OK] $($test.name) → $($res.StatusCode)" -ForegroundColor Green
        } else {
            Write-Host "[ATTENTION] $($test.name) → Réponse inattendue ($($res.StatusCode))" -ForegroundColor DarkYellow
        }
    } catch {
        Write-Host "[ERREUR] $($test.name) → Route inaccessible" -ForegroundColor Red
    }
}

# 5️⃣ Résumé
Write-Host ""
Write-Host "=============================================================" -ForegroundColor DarkYellow
Write-Host " DIAGNOSTIC TERMINE - Vérifie les lignes rouges si présentes" -ForegroundColor Yellow
Write-Host "=============================================================" -ForegroundColor DarkYellow
Write-Host ""
