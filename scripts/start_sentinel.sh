#!/bin/bash
# MOBIUS Sentinel Node — Master (Ubuntu/Linux)
# Użycie: ./scripts/start_sentinel.sh [--mode text|mic]

cd "$(dirname "$0")/.."
echo "[MOBIUS] Uruchamianie Sentinel Node..."
python node1_linux/sentinel_node.py \
  --titan-host "${TITAN_HOST:-192.168.1.249}" \
  --titan-port "${TITAN_PORT:-50051}" \
  --ollama-host "${OLLAMA_HOST:-http://localhost:11434}" \
  --mode "${MOBIUS_MODE:-text}" \
  "$@"
