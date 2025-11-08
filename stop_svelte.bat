@echo off
REM Script pour arrêter Trade Cursor v7.0

echo ========================================
echo 🛑 Stopping Trade Cursor v7.0
echo ========================================
echo.

REM Tuer tous les processus Python (backend)
echo Stopping Python backend...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Trade Cursor Backend*" 2>nul
if %ERRORLEVEL% equ 0 (
    echo ✅ Backend stopped
) else (
    echo ⚠️ No backend process found
)

REM Tuer tous les processus Node.js sur port 3000 (frontend)
echo Stopping Node.js frontend...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
    if %ERRORLEVEL% equ 0 (
        echo ✅ Frontend stopped
    )
)

REM Alternative: tuer toutes les fenêtres cmd avec titre Trade Cursor
taskkill /F /FI "WINDOWTITLE eq Trade Cursor*" 2>nul

echo.
echo ========================================
echo ✅ All servers stopped
echo ========================================
echo.
pause
