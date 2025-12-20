@echo off
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
    pause
    goto :start
)
if "%choice%"=="2" (
    echo Demarrage du mode daemon...
    python mexc_token_extractor.py daemon
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
