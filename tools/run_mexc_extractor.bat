@echo off
cd /d "%~dp0"
echo MEXC Token Extractor - Solution Permanente
echo ==========================================
echo.
echo 1. Extraction unique
echo 2. Mode daemon (continu)
echo 3. Voir configuration
echo 4. Quitter
echo.
set /p choice=Choisissez une option (1-4): 

if "%choice%"=="1" (
    python mexc_token_extractor.py once
    call :sync_token_to_env
    pause
    goto :start
)
if "%choice%"=="2" (
    echo Demarrage du mode daemon...
    python mexc_token_extractor.py daemon
    call :sync_token_to_env
    pause
    goto :start
)
if "%choice%"=="3" (
    python mexc_token_extractor.py config
    pause
    goto :start
)
if "%choice%"=="4" (
    exit
)

:start
cls
goto :EOF

:sync_token_to_env
echo.
echo === Synchronisation token vers .env ===
python sync_mexc_token.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Token synchronise avec succes dans .env
    echo ⚠️  IMPORTANT: Redemarrez le bot pour appliquer le nouveau token
) else (
    echo.
    echo ❌ Erreur lors de la synchronisation
)
echo.
goto :eof
