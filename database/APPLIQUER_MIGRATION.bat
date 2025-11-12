@echo off
REM Script pour appliquer la migration SQL complète
REM Usage: Double-cliquer sur ce fichier OU exécuter depuis PowerShell

echo ========================================
echo Application de la migration SQL
echo ========================================
echo.

REM Se déplacer dans le répertoire du script
cd /d "%~dp0"

REM Vérifier que le fichier existe
if not exist "migration_complete_all_changes.sql" (
    echo ERREUR: Fichier migration_complete_all_changes.sql introuvable
    echo Repertoire actuel: %CD%
    pause
    exit /b 1
)

echo Fichier trouve: %CD%\migration_complete_all_changes.sql
echo.
echo Connexion a PostgreSQL...
echo Base de donnees: trade_cursor_ml
echo.
echo Vous allez etre demande le mot de passe PostgreSQL
echo.

REM Appliquer la migration
psql -U postgres -d trade_cursor_ml -f migration_complete_all_changes.sql

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Migration appliquee avec succes!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERREUR lors de l'application de la migration
    echo ========================================
)

echo.
pause

