# MOBIUS — Plan Implementacji v2
*Dokument wygenerowany przed rozpoczęciem pracy. Opisuje stan obecny, delta zmian i pełną strukturę docelową.*

---

## 1. Stan obecny vs. Wymagania v2

| Element | Stan obecny (v1) | Wymaganie v2 | Akcja |
|---|---|---|---|
| Node 1 OS | Linux (generic) | **Ubuntu Server 24.04 LTS** | Brak zmian w kodzie, aktualizacja docs |
| Node 1 router | 2-tier: local \| gRPC→Titan | **3-tier: local \| Ollama (1B) \| gRPC→Titan** | `sentinel_node.py` — dodać `OllamaClient` |
| Ollama API | Brak | **localhost:11434** (szybki model 1B) | Nowa klasa + logika routingu |
| Tożsamość systemu | Częściowo (system prompt) | **System odpowiada jako MOBIUS** | Wzmocnić w system prompcie |
| `mobius.service` | Brak | **systemd unit dla Ubuntu** | Nowy plik |
| `requirements.txt` Node 1 | Kompletny | Dodać `httpx` / `requests` dla Ollama | Aktualizacja |
| `requirements.txt` Node 2 | Kompletny | Upewnić się o CUDA 12.x / Triton | Doprecyzowanie komentarzy |
| `triton_kernels.py` w `titan_node.py` | Plik istnieje, brak integracji z ModelManager | `patch_model()` musi być wywoływane po załadowaniu | `titan_node.py` — dodać wywołanie |
| `mobius.proto` | Kompletny (5 RPC) | Bez zmian | — |

---

## 2. Docelowa struktura plików

```
mobius/
├── MOBIUS_PLAN.md                ← ten plik
├── README.md
│
├── proto/
│   └── mobius.proto              ← gRPC definition (bez zmian)
│
├── generated/                    ← wypełniane przez protoc
│   ├── mobius_pb2.py
│   └── mobius_pb2_grpc.py
│
├── node1_linux/
│   ├── sentinel_node.py          ← ZAKTUALIZOWANY: +OllamaClient, 3-tier router
│   ├── requirements.txt          ← ZAKTUALIZOWANY: +httpx
│   └── mobius.service            ← NOWY: systemd unit
│
└── node2_windows/
    ├── titan_node.py             ← ZAKTUALIZOWANY: +patch_model() integracja
    ├── triton_kernels.py         ← bez zmian
    └── requirements.txt          ← bez zmian
```

---

## 3. Architektura — przepływ danych

```
[Mikrofon / Terminal]
        │
        ▼
 VAD (WebRTC) → faster-whisper
        │
        ▼
  classify_intent(text)
        │
   ┌────┼────────────┐
   │    │            │
local  ollama      gRPC
bash   1B model    Titan
cmd    (fast)      (complex)
   │    │            │
   └────┴────────────┘
        │
        ▼
  MOBIUS odpowiada
```

### Logika klasyfikacji (3-tier)

| Warunek | Cel | Przykład |
|---|---|---|
| Regex: komenda systemowa | `local` → subprocess | `ls -la`, `ping 8.8.8.8` |
| Krótkie pytanie / proste zdanie ≤ 80 znaków | `ollama` → localhost:11434 | "Jaka jest stolica Francji?" |
| Długi prompt / reasoning / kod | `titan` → gRPC Node 2 | "Napisz mi klasę Python do..." |

---

## 4. Ollama Client — specyfikacja

```python
POST http://localhost:11434/api/generate
{
  "model": "llama3.2:1b",   # lub "qwen2.5:1.5b" — konfigurowalny
  "prompt": "...",
  "system": "Jesteś MOBIUS...",
  "stream": false
}
```

- Timeout: 30s
- Fallback: jeśli Ollama niedostępna → przejdź do Titan
- Model domyślny: `llama3.2:1b` (konfigurowalny przez env `OLLAMA_MODEL`)

---

## 5. mobius.service — systemd spec

```ini
[Unit]
Description=MOBIUS Sentinel Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mobius                          # dedykowany użytkownik
WorkingDirectory=/opt/mobius
ExecStart=/opt/mobius/venv/bin/python node1_linux/sentinel_node.py --mode text
Restart=on-failure
RestartSec=5
Environment=TITAN_HOST=192.168.1.100
Environment=TITAN_PORT=50051
Environment=OLLAMA_HOST=http://localhost:11434

[Install]
WantedBy=multi-user.target
```

---

## 6. VRAM Purge — sekwencja (bez zmian, dla dokumentacji)

```
Po każdej inferencji na Node 2:

  del self._model          # 1. usuń referencję Python
  del self._tokenizer
  gc.collect()             # 2. GC pass 1
  torch.cuda.empty_cache() # 3. zwróć pulę CUDA → OS
  torch.cuda.synchronize() # 4. opróżnij strumień CUDA
  gc.collect()             # 5. GC pass 2

  Cel: 0 MB VRAM w stanie idle
```

---

## 7. Triton Kernels — integracja (brakujący element v1)

W `ModelManager.load()` dodać po `self._model.eval()`:

```python
from triton_kernels import patch_model
counts = patch_model(self._model, verbose=True)
log.info("Triton patches: %s", counts)
```

Obsługiwane klasy modeli: `LlamaRMSNorm`, `MistralRMSNorm`, `Qwen2RMSNorm`, `GemmaRMSNorm`, `LlamaMLP`, `MistralMLP`, `Qwen2MLP`.

---

## 8. Zmienne środowiskowe — pełna lista

### Node 1 (Linux)
| Zmienna | Domyślna | Opis |
|---|---|---|
| `TITAN_HOST` | `192.168.1.249` | IP Node 2 (Windows PC) |
| `TITAN_PORT` | `50051` | Port gRPC Titan |
| `OLLAMA_HOST` | `http://localhost:11434` | Adres Ollama API |
| `OLLAMA_MODEL` | `llama3.2:1b` | Model 1B w Ollama |
| `MOBIUS_MODE` | `text` | `text` \| `mic` |
| `WHISPER_MODEL` | `base.en` | Model Whisper |

### Node 2 (Windows)
| Zmienna | Domyślna | Opis |
|---|---|---|
| `TITAN_DEFAULT_MODEL` | `mistralai/Mistral-7B-Instruct-v0.3` | Model HuggingFace |

---

## 9. Kolejność implementacji

1. [x] `MOBIUS_PLAN.md` — ten dokument
2. [ ] `sentinel_node.py` — dodać `OllamaClient`, zaktualizować `classify_intent` i `_dispatch`
3. [ ] `titan_node.py` — dodać `patch_model()` w `ModelManager.load()`
4. [ ] `node1_linux/mobius.service` — nowy plik systemd
5. [ ] `node1_linux/requirements.txt` — dodać `httpx`
6. [ ] `node2_windows/requirements.txt` — doprecyzować komentarze CUDA 12.x

---

## 10. Komendy startowe

### Generowanie stubów gRPC (raz)
```bash
cd /opt/mobius
python -m grpc_tools.protoc \
  -I proto \
  --python_out=generated \
  --grpc_python_out=generated \
  proto/mobius.proto
```

### Node 2 — Titan (Windows, PowerShell)
```powershell
$env:TITAN_DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
python node2_windows\titan_node.py --host 0.0.0.0 --port 50051
```

### Node 1 — Sentinel (Ubuntu, ręcznie)
```bash
python node1_linux/sentinel_node.py \
  --titan-host 192.168.1.249 \
  --mode text
```

### Node 1 — Sentinel (Ubuntu, systemd)
```bash
sudo systemctl enable mobius
sudo systemctl start mobius
sudo journalctl -u mobius -f
```
