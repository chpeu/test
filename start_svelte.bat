@echo off
REM Script de démarrage Trade Cursor v7.0 avec frontend Svelte - Windows

echo ========================================
echo 🚀 Starting Trade Cursor v7.0 with Svelte Frontend
echo ========================================
echo.

REM Vérifier si on est dans le bon répertoire
if not exist "main.py" (
    echo ❌ Error: main.py not found
    echo Please run this script from trade_cursor_py directory
    pause
    exit /b 1
)

REM Vérifier si le dossier frontend existe
if not exist "frontend" (
    echo ❌ Error: frontend directory not found
    pause
    exit /b 1
)

REM Vérifier Node.js
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: Node.js is not installed
    echo Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)

echo ✅ Node.js version:
node -v
echo.

REM Vérifier Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: Python is not installed
    echo Please install Python 3.11+ from https://www.python.org
    pause
    exit /b 1
)

echo ✅ Python version:
python --version
echo.

REM Installer les dépendances frontend si nécessaire
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo ❌ Error: npm install failed
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo ✅ Dependencies installed
    echo.
)

REM Démarrer le backend en arrière-plan
echo 🐍 Starting FastAPI backend (port 5000)...
start "Trade Cursor Backend" /MIN python main.py

REM Attendre que le backend démarre
timeout /t 3 /nobreak >nul

echo ✅ Backend started
echo.

REM Démarrer le frontend
echo ⚡ Starting Svelte frontend (port 3000)...
cd frontend
start "Trade Cursor Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo 🎉 Trade Cursor v7.0 is running!
echo.
echo 📍 Frontend:  http://localhost:3000
echo 📍 Backend:   http://localhost:5000
echo 📍 API:       http://localhost:5000/api/state
echo.
echo Two command windows have been opened:
echo - Backend (minimized)
echo - Frontend (visible)
echo.
echo Close both windows to stop the servers
echo ========================================
echo.
pause
