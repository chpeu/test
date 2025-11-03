@echo off
echo ============================================
echo  Lancement de 3 instances simultanees
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Demarrage Instance 1 (Port 5000)...
start "Instance 1 - Port 5000" python main.py 5000
timeout /t 2 /nobreak > nul

echo [2/3] Demarrage Instance 2 (Port 5001)...
start "Instance 2 - Port 5001" python main.py 5001
timeout /t 2 /nobreak > nul

echo [3/3] Demarrage Instance 3 (Port 5002)...
start "Instance 3 - Port 5002" python main.py 5002
timeout /t 2 /nobreak > nul

echo.
echo ============================================
echo  ✅ Instances lancees!
echo ============================================
echo.
echo 🌐 http://localhost:5000 - Instance 1
echo 🌐 http://localhost:5001 - Instance 2
echo 🌐 http://localhost:5002 - Instance 3
echo.
echo Appuyez sur une touche pour fermer cette fenetre...
pause > nul



