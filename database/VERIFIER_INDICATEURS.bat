@echo off
REM Script pour vérifier les indicateurs d'entrée dans PostgreSQL

cd /d "%~dp0\.."
python database\verifier_indicators.py
pause

