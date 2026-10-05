@echo off
title SQL Database Verification
cd /d "c:\Users\sebta\Documents\clone github\test\test"

echo ========================================
echo   SQL DATABASE VERIFICATION CHECKER
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
echo 🚀 Lancement de la vérification base de données...
echo.
python scripts\verify_sql_database_filling.py

echo.
echo ========================================
echo   VÉRIFICATION TERMINÉE
echo ========================================
pause
