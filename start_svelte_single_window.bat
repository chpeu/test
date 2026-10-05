@echo off
REM Script de démarrage Trade Cursor v7.0 - Version fenêtre unique
REM ATTENTION: Ctrl+C fermera les deux serveurs

echo ========================================
echo 🚀 Trade Cursor v7.0 - Single Window Mode
echo ========================================
echo.

REM Vérifications (même que version 2 fenêtres)
if not exist "main.py" (
    echo ❌ Error: main.py not found
    pause
    exit /b 1
)

if not exist "frontend" (
    echo ❌ Error: frontend directory not found
    pause
    exit /b 1
)

where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: Node.js not installed
    pause
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: Python not installed
    pause
    exit /b 1
)

if not exist "logs" (
    mkdir logs
)

REM Installer dépendances si nécessaire
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo ✅ Starting backend and frontend...
echo.
echo 📍 Frontend:  http://localhost:3000
echo 📍 Backend:   http://localhost:5000
echo 📄 Watchdog log: logs\backend_watchdog.log
echo.
echo Press Ctrl+C to stop both servers
echo ========================================
echo.

REM Créer script temporaire pour lancer les deux
echo @echo off > temp_start.bat
echo start /B python backend_watchdog.py >> temp_start.bat
echo cd frontend >> temp_start.bat
echo npm run dev >> temp_start.bat

REM Lancer
call temp_start.bat

REM Nettoyer
del temp_start.bat
