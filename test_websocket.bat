@echo off
chcp 65001 >nul
echo ==================================================
echo Test et Demarrage WebSocket
echo ==================================================
echo.

cd /d "%~dp0"

python test_websocket_start.py

pause


