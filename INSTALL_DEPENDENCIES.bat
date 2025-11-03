@echo off
echo ====================================
echo Installation dependances Trade Cursor v6.6.1
echo ====================================
echo.

cd /d "%~dp0"

echo Verification Python...
python --version
echo.

echo Installation des dependances...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ====================================
echo Installation terminee!
echo ====================================
echo.
pause

