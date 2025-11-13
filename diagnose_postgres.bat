@echo off
echo === DIAGNOSTIC POSTGRESQL DATALOGGER (WINDOWS) ===
echo.

echo 1. Verification fichier .env
if exist .env (
    echo [OK] .env existe
    findstr POSTGRES .env
) else (
    echo [ERREUR] .env n'existe pas
)
echo.

echo 2. Test connexion PostgreSQL
set PGPASSWORD=
psql -h localhost -U postgres -d trade_cursor_ml -c "SELECT 'Connected' as status;" 2>nul
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL connecte
) else (
    echo [ERREUR] PostgreSQL non connecte
)
echo.

echo 3. Nombre de scans/opportunites/trades
psql -h localhost -U postgres -d trade_cursor_ml -c "SELECT 'scan_logs' as table_name, COUNT(*) as count FROM scan_logs UNION ALL SELECT 'opportunities', COUNT(*) FROM opportunities UNION ALL SELECT 'trades', COUNT(*) FROM trades;" 2>nul
echo.

echo 4. Verifier si le bot tourne
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *main.py*" 2>nul | find "python.exe" >nul
if %errorlevel% equ 0 (
    echo [OK] Bot Python en cours d'execution
) else (
    echo [ERREUR] Bot non demarre
)
echo.

echo === INSTRUCTIONS WINDOWS ===
echo.
echo Si PostgreSQL non connecte:
echo   1. Ouvrir Services Windows (services.msc)
echo   2. Chercher "postgresql-x64-XX" (XX = version)
echo   3. Clic droit ^> Demarrer
echo   OU via ligne de commande:
echo   net start postgresql-x64-XX
echo.
echo Si bot non demarre:
echo   python main.py 5000
echo.
echo Verifier les logs:
echo   type logs\*.log ^| findstr "Thread de flush"
echo   type logs\*.log ^| findstr "PostgreSQL"
echo.
pause
