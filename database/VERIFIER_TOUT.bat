@echo off
REM Script pour lancer la vérification complète du datalogger PostgreSQL
REM Usage: Double-cliquer sur ce fichier

echo ========================================
echo Verification Complete - PostgreSQL Datalogger
echo ========================================
echo.

REM Se déplacer dans le répertoire du projet
cd /d "C:\Users\sebta\Documents\clone github\test\test"

REM Vérifier que le répertoire existe
if not exist "database\verify_all.py" (
    echo ERREUR: Fichier verify_all.py introuvable
    echo Repertoire actuel: %CD%
    pause
    exit /b 1
)

echo Repertoire: %CD%
echo.
echo Lancement de la verification...
echo.

REM Lancer le script Python
python database\verify_all.py

REM Attendre la fin du script
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Verification terminee avec succes!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERREUR lors de la verification
    echo ========================================
)

echo.
pause

