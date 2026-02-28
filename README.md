# MOBIUS — Distributed AI System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Lokalne centrum dowodzenia w stylu JARVIS/FRIDAY — autonomiczny AGI.

```
Node 1 (Linux/Sentinel) ──── gRPC ────► Node 2 (Windows/Titan)
  faster-whisper + VAD               RTX 5060 Ti | 4-bit LLM
  local subprocess router            Hard VRAM purge after infer
```

**GitHub:** [github.com/pontonempopokojuXD/mobius](https://github.com/pontonempopokojuXD/mobius)

---

## Architecture

| | Node 1 — Sentinel | Node 2 — Titan |
|---|---|---|
| **OS** | Linux | Windows |
| **Hardware** | CPU-only | RTX 5060 Ti |
| **Role** | Master / Router | Worker / Inference |
| **Key files** | `sentinel_node.py` | `titan_node.py`, `triton_kernels.py` |
| **Transport** | gRPC client | gRPC server :50051 |

---

## File Structure

```
mobius/
├── proto/
│   └── mobius.proto              # gRPC service definition
├── generated/
│   ├── mobius_pb2.py             # (generated) protobuf stubs
│   └── mobius_pb2_grpc.py        # (generated) gRPC stubs
├── mobius_gui.py                 # GUI — centrum dowodzenia (Ollama + Titan)
├── mobius_agent.py               # Agent ReAct — narzędzia (pliki, RAG, shell)
├── mobius_voice.py               # STT (mikrofon) + TTS (edge-tts)
├── mobius_rag.py                # Baza wiedzy (ChromaDB)
├── mobius_reminders.py          # Przypomnienia
├── mobius_titan_client.py       # Klient gRPC do Titan (backend GUI)
├── mobius_config.json           # Konfiguracja GUI
├── requirements_gui.txt         # Zależności GUI
├── MOBIUS_ROADMAP.md            # Roadmap do JARVIS/FRIDAY
├── DEPLOY.md                    # Przewodnik wdrożenia
├── scripts/
│   ├── setup_gui.bat            # Instalacja zależności GUI
│   ├── start_gui.bat            # Uruchom GUI
│   ├── start_titan.bat          # Uruchom Titan Node
│   └── start_sentinel.sh        # Uruchom Sentinel (Linux)
├── node1_linux/
│   ├── sentinel_node.py         # Master: VAD + Whisper + router
│   └── requirements.txt
└── node2_windows/
    ├── titan_node.py            # Worker: gRPC + LLM + VRAM purge
    ├── triton_kernels.py       # Fused RMSNorm + SwiGLU
    └── requirements.txt
```

---

## Step 1 — Generate gRPC Stubs (run once, either node)

```bash
pip install grpcio-tools

python -m grpc_tools.protoc \
  -I proto \
  --python_out=generated \
  --grpc_python_out=generated \
  proto/mobius.proto
```

---

## GUI — Lokalne Centrum Dowodzenia (Windows)

```powershell
pip install -r requirements_gui.txt
python mobius_gui.py
```

**Funkcje:** streaming odpowiedzi, głos (STT/TTS), tryb Agent (ReAct), backend Ollama lub Titan.

| Funkcja | Opis |
|---------|------|
| **Streaming** | Odpowiedzi token po tokenie |
| **Głos** | Mikrofon (STT) + Odtwarzanie (TTS, edge-tts) |
| **Agent** | ReAct + narzędzia: pliki, RAG, przypomnienia, shell |
| **Backend** | Ollama (szybkie) lub Titan (modele 7B+) |

**Wymaga:** Ollama na `http://localhost:11434`. Opcjonalnie Titan (gRPC :50051) dla większych modeli.

### Narzędzia agenta

| Narzędzie | Opis |
|-----------|------|
| `read_file`, `write_file`, `list_dir` | Pliki |
| `add_reminder(text, when)` | Przypomnienia |
| `rag_search(query)`, `rag_add(text)`, `rag_add_file(path)` | Baza wiedzy |
| `run_shell(command)` | PowerShell (wymaga włączenia w config) |

---

## Step 2 — Node 2 Setup (Windows / Titan)

### 2a. Install PyTorch with CUDA 12.4

```powershell
pip install torch torchvision torchaudio `
  --index-url https://download.pytorch.org/whl/cu124
```

### 2b. Install BitsAndBytes (Windows wheel)

```powershell
pip install bitsandbytes --prefer-binary `
  --extra-index-url https://jllllll.github.io/bitsandbytes-windows-webui
```

### 2c. Install FlashAttention-3 (Windows pre-built)

Download the matching wheel for your Python + CUDA from:  
https://github.com/bdashore3/flash-attention/releases

```powershell
pip install flash_attn-*.whl
```

### 2d. Install Triton for Windows

```powershell
# Option A – pip (may have a preview build)
pip install triton

# Option B – community Windows wheel
# https://github.com/woct0rdho/triton-windows/releases
pip install triton_windows-*.whl
```

### 2e. Install remaining dependencies

```powershell
pip install -r node2_windows\requirements.txt
```

### 2f. Start Titan Node

```powershell
# Default model via env var (optional)
$env:TITAN_DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"

python node2_windows\titan_node.py --host 0.0.0.0 --port 50051
```

Titan starts **idle** — no model in VRAM until the first request arrives.

---

## Step 3 — Node 1 Setup (Linux / Sentinel)

### 3a. System dependencies

```bash
sudo apt install portaudio19-dev libsndfile1
```

### 3b. Python dependencies

```bash
pip install -r node1_linux/requirements.txt
```

### 3c. Start Sentinel (text REPL mode)

```bash
python node1_linux/sentinel_node.py \
  --titan-host 192.168.1.249 \
  --titan-port 50051 \
  --mode text
```

### 3d. Start Sentinel (live microphone mode)

```bash
python node1_linux/sentinel_node.py \
  --titan-host 192.168.1.249 \
  --titan-port 50051 \
  --mode mic \
  --whisper-model base.en \
  --language en
```

---

## VRAM Purge Logic (Node 2)

Every inference call follows this exact sequence:

```
1. Request arrives
2. Load model  (4-bit NF4 + bfloat16 + FlashAttention-3)
3. Run inference
4. ── HARD PURGE ──────────────────────────────────────
   a. del model / del tokenizer
   b. gc.collect()              ← free Python-side refs
   c. torch.cuda.empty_cache()  ← return CUDA pool → OS
   d. torch.cuda.synchronize()  ← flush CUDA stream
   e. gc.collect()              ← catch CUDA callback refs
5. Idle: 0 MB VRAM
```

You can also trigger a manual purge from Sentinel:

```
› !purge
Purged: 14432.0 MB freed
```

---

## Triton Kernel Patches (Node 2)

Triton kernels are applied automatically inside `titan_node.py` after model load.  
To apply manually:

```python
from triton_kernels import patch_model
counts = patch_model(model, verbose=True)
# [triton_kernels] Patched 32 RMSNorm and 32 SwiGLU modules.
```

Supported model families: Llama, Mistral, Qwen2, Gemma, Phi.

---

## Sentinel REPL Commands

| Input | Action |
|---|---|
| Any natural language | Routed to Titan (LLM) |
| Shell command (e.g. `ls -la`) | Executed locally via subprocess |
| `!health` | Print Titan VRAM/GPU status |
| `!purge` | Force-purge VRAM on Titan |
| `exit` / `quit` | Shut down Sentinel |

---

## Environment Variables

| Variable | Node | Default | Description |
|---|---|---|---|
| `TITAN_DEFAULT_MODEL` | 2 | `mistralai/Mistral-7B-Instruct-v0.3` | Default model ID |
| `TITAN_HOST` | 1 | `192.168.1.100` | Titan IP for Sentinel |
| `TITAN_PORT` | 1 | `50051` | Titan gRPC port |

---

## gRPC Service Summary

```protobuf
service TitanService {
  rpc Infer        (InferRequest)  returns (InferResponse);      // blocking
  rpc InferStream  (InferRequest)  returns (stream InferChunk);  // streaming
  rpc HealthCheck  (HealthRequest) returns (HealthResponse);
  rpc PurgeVRAM    (PurgeRequest)  returns (PurgeResponse);
  rpc WarmUp       (WarmUpRequest) returns (WarmUpResponse);
}
```
