@echo off
title MEXC Requests Statistics
cd /d "c:\Users\sebta\Documents\clone github\test\test"

echo ========================================
echo   MEXC REQUESTS STATISTICS CHECKER
echo ========================================
echo.

REM Vérifier si Python est disponible
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    pause
    exit /b 1
)

REM Exécuter le script
echo 🚀 Lancement du script de statistiques MEXC...
echo.
python scripts\check_mexc_requests_stats.py

echo.
echo ========================================
echo   SCRIPT TERMINÉ
echo ========================================
pause
