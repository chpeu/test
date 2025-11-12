# Script PowerShell pour appliquer la migration SQL complète
# Usage: .\APPLIQUER_MIGRATION.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Application de la migration SQL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Se déplacer dans le répertoire du script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Vérifier que le fichier existe
$migrationFile = Join-Path $scriptDir "migration_complete_all_changes.sql"
if (-not (Test-Path $migrationFile)) {
    Write-Host "ERREUR: Fichier migration_complete_all_changes.sql introuvable" -ForegroundColor Red
    Write-Host "Répertoire actuel: $PWD" -ForegroundColor Red
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

Write-Host "Fichier trouvé: $migrationFile" -ForegroundColor Green
Write-Host ""
Write-Host "Connexion à PostgreSQL..." -ForegroundColor Yellow
Write-Host "Base de données: trade_cursor_ml" -ForegroundColor Yellow
Write-Host ""
Write-Host "Vous allez être demandé le mot de passe PostgreSQL" -ForegroundColor Yellow
Write-Host ""

# Appliquer la migration
$env:PGPASSWORD = Read-Host "Mot de passe PostgreSQL" -AsSecureString | ConvertFrom-SecureString -AsPlainText
$result = & psql -U postgres -d trade_cursor_ml -f $migrationFile 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Migration appliquée avec succès!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "ERREUR lors de l'application de la migration" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host $result -ForegroundColor Red
}

Write-Host ""
Read-Host "Appuyez sur Entrée pour quitter"

