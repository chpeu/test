# Script PowerShell de diagnostic PostgreSQL DataLogger

Write-Host "=== DIAGNOSTIC POSTGRESQL DATALOGGER (WINDOWS) ===" -ForegroundColor Cyan
Write-Host ""

# 1. Vérifier .env
Write-Host "1. Verification fichier .env" -ForegroundColor Yellow
if (Test-Path .env) {
    Write-Host "[OK] .env existe" -ForegroundColor Green
    Get-Content .env | Select-String "POSTGRES"
} else {
    Write-Host "[ERREUR] .env n'existe pas" -ForegroundColor Red
}
Write-Host ""

# 2. Vérifier service PostgreSQL
Write-Host "2. Verification service PostgreSQL" -ForegroundColor Yellow
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if ($pgService) {
    Write-Host "[OK] Service PostgreSQL trouve: $($pgService.Name)" -ForegroundColor Green
    Write-Host "    Status: $($pgService.Status)" -ForegroundColor $(if($pgService.Status -eq 'Running'){'Green'}else{'Red'})

    if ($pgService.Status -ne 'Running') {
        Write-Host ""
        Write-Host "Pour demarrer PostgreSQL:" -ForegroundColor Yellow
        Write-Host "  Start-Service $($pgService.Name)" -ForegroundColor White
        Write-Host "  OU: net start $($pgService.Name)" -ForegroundColor White
    }
} else {
    Write-Host "[ERREUR] Service PostgreSQL non trouve" -ForegroundColor Red
    Write-Host "PostgreSQL n'est peut-etre pas installe" -ForegroundColor Yellow
}
Write-Host ""

# 3. Test connexion PostgreSQL
Write-Host "3. Test connexion PostgreSQL" -ForegroundColor Yellow
$env:PGPASSWORD = ""
try {
    $result = & psql -h localhost -U postgres -d trade_cursor_ml -c "SELECT 'Connected' as status;" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Connexion reussie" -ForegroundColor Green
    } else {
        Write-Host "[ERREUR] Connexion echouee" -ForegroundColor Red
        Write-Host $result
    }
} catch {
    Write-Host "[ERREUR] psql non trouve ou erreur connexion" -ForegroundColor Red
}
Write-Host ""

# 4. Compter scans/opportunités/trades
Write-Host "4. Nombre de scans/opportunites/trades" -ForegroundColor Yellow
try {
    & psql -h localhost -U postgres -d trade_cursor_ml -c "SELECT 'scan_logs' as table_name, COUNT(*) as count FROM scan_logs UNION ALL SELECT 'opportunities', COUNT(*) FROM opportunities UNION ALL SELECT 'trades', COUNT(*) FROM trades;" 2>&1
} catch {
    Write-Host "[ERREUR] Impossible d'interroger la base" -ForegroundColor Red
}
Write-Host ""

# 5. Vérifier processus Python
Write-Host "5. Verification bot Python" -ForegroundColor Yellow
$pythonProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*main.py*" }
if ($pythonProcess) {
    Write-Host "[OK] Bot en cours d'execution (PID: $($pythonProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Bot non demarre" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== INSTRUCTIONS ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pour demarrer le bot:" -ForegroundColor Yellow
Write-Host "  python main.py 5000" -ForegroundColor White
Write-Host ""
Write-Host "Verifier les logs:" -ForegroundColor Yellow
Write-Host "  Get-Content logs\*.log | Select-String 'Thread de flush'" -ForegroundColor White
Write-Host "  Get-Content logs\*.log | Select-String 'PostgreSQL'" -ForegroundColor White
Write-Host ""
