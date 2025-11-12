# Script PowerShell d'installation PostgreSQL - Trade Cursor
# Usage: .\install.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 Installation PostgreSQL - Trade Cursor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$dbName = "trade_cursor_ml"
$projectPath = "C:\Users\sebta\Documents\clone github\test\test"
$schemaFile = Join-Path $projectPath "database\schema_postgresql_complete.sql"

# Vérifier que le fichier existe
if (-not (Test-Path $schemaFile)) {
    Write-Host "❌ Erreur : Fichier schema non trouvé : $schemaFile" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Étape 1 : Suppression de l'ancienne base (si existe)..." -ForegroundColor Yellow
try {
    psql -U postgres -c "DROP DATABASE IF EXISTS $dbName;" 2>&1 | Out-Null
    Write-Host "✅ Ancienne base supprimée" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Erreur lors de la suppression (peut être normal si n'existe pas)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📋 Étape 2 : Création de la base de données..." -ForegroundColor Yellow
try {
    psql -U postgres -c "CREATE DATABASE $dbName;" 2>&1 | Out-Null
    Write-Host "✅ Base de données créée : $dbName" -ForegroundColor Green
} catch {
    Write-Host "❌ Erreur lors de la création de la base" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 Étape 3 : Exécution du schéma SQL..." -ForegroundColor Yellow
Write-Host "   Fichier : $schemaFile" -ForegroundColor Gray

try {
    $output = psql -U postgres -d $dbName -f $schemaFile 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Schéma exécuté avec succès !" -ForegroundColor Green
    } else {
        Write-Host "❌ Erreur lors de l'exécution du schéma" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Erreur : $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 Étape 4 : Vérification..." -ForegroundColor Yellow

try {
    $tables = psql -U postgres -d $dbName -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>&1
    $tables = $tables.Trim()
    
    Write-Host "✅ Tables créées : $tables" -ForegroundColor Green
    
    # Lister les tables
    Write-Host ""
    Write-Host "📊 Tables dans la base :" -ForegroundColor Cyan
    psql -U postgres -d $dbName -c "\dt" 2>&1
    
} catch {
    Write-Host "⚠️  Impossible de vérifier (mais l'installation semble réussie)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Installation terminée !" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Pour vous connecter :" -ForegroundColor Yellow
Write-Host "   psql -U postgres -d $dbName" -ForegroundColor White
Write-Host ""


