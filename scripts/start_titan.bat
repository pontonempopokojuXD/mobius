@echo off
REM MOBIUS Titan Node — gRPC inference server (Windows)
REM Wymaga: PyTorch CUDA, BitsAndBytes, FlashAttention, Triton

cd /d "%~dp0\.."
echo [MOBIUS] Uruchamianie Titan Node...
python node2_windows\titan_node.py --host 0.0.0.0 --port 50051
pause
