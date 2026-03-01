@echo off
cd /d "%~dp0\.."
echo [MOBIUS] Uruchamianie API na porcie 5000...
python mobius_api.py --port 5000
pause
