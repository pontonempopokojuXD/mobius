@echo off
REM MOBIUS Titan Node — gRPC inference server (Windows)
REM Wymaga: PyTorch CUDA, BitsAndBytes, FlashAttention, Triton
REM Opcjonalnie: set TITAN_MAX_VRAM_FRACTION=0.65 (domyslnie 0.70 = max ~11 GB)
REM set PYTORCH_ALLOC_CONF=expandable_segments:True — redukuje fragmentacje VRAM

cd /d "%~dp0\.."
echo [MOBIUS] Uruchamianie Titan Node...
python node2_windows\titan_node.py --host 0.0.0.0 --port 50051
pause
