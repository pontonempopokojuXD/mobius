#!/bin/bash
# MOBIUS GUI — Instalacja zależności (Linux)

cd "$(dirname "$0")/.."
echo "[MOBIUS] Instalacja zależności GUI..."
pip install -r requirements_gui.txt
echo "[MOBIUS] Gotowe. Uruchom: python mobius_gui.py"
