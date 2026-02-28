@echo off
REM MOBIUS GUI — Lokalne Centrum Dowodzenia
REM Uruchom z katalogu głównego projektu: scripts\start_gui.bat

cd /d "%~dp0\.."
echo [MOBIUS] Uruchamianie GUI...
python mobius_gui.py
pause
