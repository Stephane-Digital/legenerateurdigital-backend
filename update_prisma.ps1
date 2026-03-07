# =====================================================================
# UPDATE_PRISMA.PS1 — Le Générateur Digital (Backend)
# ---------------------------------------------------------------------
# 🚀 Version Ultra-Secure Deluxe :
# ✅ Sauvegarde automatique horodatée
# ✅ Formatage, synchronisation Render et génération du client Python
# ✅ Vérification automatique du client Prisma
# ✅ Options de maintenance :
#    -restore dernier → restaure la dernière sauvegarde (avec confirmation)
#    -list             → liste les sauvegardes disponibles
# =====================================================================

param (
    [string]$restore,
    [switch]$list
)

Write-Host ""
Write-Host "=== Le Generateur Digital - Maintenance Prisma (Ultra-Secure Deluxe) ===" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------"

# 📂 Dossiers de travail
$schemaPath = "prisma\schema.prisma"
$backupDir = "prisma\backups"

# =====================================================================
# 1️⃣ GESTION DES OPTIONS : LISTE / RESTAURATION
# =====================================================================

# 📜 Liste des sauvegardes disponibles
if ($list) {
    if (Test-Path $backupDir) {
        Write-Host "`n📂 Sauvegardes disponibles :" -ForegroundColor Cyan
        Get-ChildItem -Path $backupDir -Filter "*.prisma" | Sort-Object LastWriteTime -Descending | ForEach-Object {
            Write-Host "🗂️  $($_.Name) — $($_.LastWriteTime)"
        }
    } else {
        Write-Host "`n⚠️ Aucun dossier de sauvegarde trouvé ($backupDir)" -ForegroundColor Red
    }
    exit 0
}

# 🛟 Restauration de la dernière sauvegarde avec confirmation
if ($restore -eq "dernier") {
    if (Test-Path $backupDir) {
        $latestBackup = Get-ChildItem -Path $backupDir -Filter "*.prisma" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latestBackup) {
            Write-Host "`nDernière sauvegarde détectée : $($latestBackup.Name)" -ForegroundColor Cyan
            $confirmation = Read-Host "⚠️ Confirmer la restauration de ce fichier ? (o/n)"
            if ($confirmation -eq "o" -or $confirmation -eq "O") {
                Copy-Item $latestBackup.FullName $schemaPath -Force
                Write-Host "`n✅ Sauvegarde restaurée : $($latestBackup.Name)" -ForegroundColor Green
            } else {
                Write-Host "`n❌ Restauration annulée par l’utilisateur." -ForegroundColor Yellow
            }
        } else {
            Write-Host "`n⚠️ Aucune sauvegarde trouvée à restaurer." -ForegroundColor Red
        }
    } else {
        Write-Host "`n⚠️ Aucun dossier de sauvegarde trouvé." -ForegroundColor Red
    }
    exit 0
}

# =====================================================================
# 2️⃣ SAUVEGARDE AUTOMATIQUE AVANT MISE À JOUR
# =====================================================================
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

if (Test-Path $schemaPath) {
    $backupPath = "$backupDir\schema_$timestamp.prisma"
    Copy-Item $schemaPath $backupPath -Force
    Write-Host "`n💾 Sauvegarde effectuée : $backupPath" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ Aucun fichier schema.prisma trouvé pour la sauvegarde." -ForegroundColor Red
}

# =====================================================================
# 3️⃣ PROCESSUS DE MISE À JOUR PRISMA
# =====================================================================
$venvPath = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "`nActivation de l'environnement virtuel..." -ForegroundColor Cyan
    & $venvPath
} else {
    Write-Host "`n⚠️ Environnement virtuel non trouvé (.venv). Active-le manuellement." -ForegroundColor Red
    exit 1
}

Write-Host "`nFormatage du schéma Prisma..." -ForegroundColor Cyan
npx prisma format

Write-Host "`nSynchronisation avec Render (db push)..." -ForegroundColor Cyan
npx prisma db push

Write-Host "`nGénération du client Prisma Python..." -ForegroundColor Cyan
prisma generate

Write-Host "`nVérification du client Prisma Python..." -ForegroundColor Cyan
python -c "from prisma import Prisma; print('✅ Prisma Python opérationnel et prêt à l’emploi')"

Write-Host ""
Write-Host "✅ Mise à jour Prisma terminée avec succès (version Ultra-Secure Deluxe) !" -ForegroundColor Green
Write-Host "----------------------------------------------------------------------"
Write-Host ""
