@echo off
REM MOBIUS GUI — Instalacja zależności
REM Uruchom z katalogu głównego: scripts\setup_gui.bat

cd /d "%~dp0\.."
echo [MOBIUS] Instalacja zależności GUI...

pip install -r requirements_gui.txt

echo.
echo [MOBIUS] Opcjonalnie - PyAudio (mikrofon dla STT):
echo   pip install pipwin
echo   pipwin install pyaudio
echo.
echo [MOBIUS] Gotowe. Uruchom: python mobius_gui.py
pause
