# Script PowerShell pour appliquer la migration des paramètres de scalabilité
# Usage: .\apply_migration_scalability.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Migration: Paramètres de Scalabilité" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier si le fichier de migration existe
$migrationFile = "database\migration_add_scalability_params.sql"
if (-not (Test-Path $migrationFile)) {
    Write-Host "❌ Erreur: Fichier de migration non trouvé: $migrationFile" -ForegroundColor Red
    Write-Host "   Assurez-vous d'être dans le répertoire du projet." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Fichier de migration trouvé: $migrationFile" -ForegroundColor Green
Write-Host ""

# Demander le mot de passe PostgreSQL
$password = Read-Host "Entrez le mot de passe PostgreSQL pour l'utilisateur 'postgres'" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

# Définir la variable d'environnement PGPASSWORD
$env:PGPASSWORD = $passwordPlain

Write-Host ""
Write-Host "📊 Application de la migration..." -ForegroundColor Yellow
Write-Host ""

# Exécuter la migration
try {
    $result = & psql -U postgres -d trade_cursor_ml -f $migrationFile 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Migration appliquée avec succès!" -ForegroundColor Green
        Write-Host ""
        
        # Vérifier que les colonnes ont été ajoutées
        Write-Host "🔍 Vérification des colonnes ajoutées..." -ForegroundColor Yellow
        $checkQuery = @"
SELECT 
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'recent_volume'
    ) THEN '✅ recent_volume' ELSE '❌ recent_volume' END as scan_logs_recent_volume,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'vol5'
    ) THEN '✅ vol5' ELSE '❌ vol5' END as scan_logs_vol5,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'scalability_score'
    ) THEN '✅ scalability_score' ELSE '❌ scalability_score' END as scan_logs_score,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'entry_recent_volume'
    ) THEN '✅ entry_recent_volume' ELSE '❌ entry_recent_volume' END as trades_recent_volume,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'entry_scalability_score'
    ) THEN '✅ entry_scalability_score' ELSE '❌ entry_scalability_score' END as trades_score;
"@
        
        $checkResult = & psql -U postgres -d trade_cursor_ml -c $checkQuery 2>&1
        Write-Host $checkResult
        
    } else {
        Write-Host ""
        Write-Host "❌ Erreur lors de l'application de la migration" -ForegroundColor Red
        Write-Host $result
    }
} catch {
    Write-Host ""
    Write-Host "❌ Erreur: $_" -ForegroundColor Red
} finally {
    # Nettoyer la variable d'environnement
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan

