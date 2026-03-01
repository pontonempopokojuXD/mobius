# MOBIUS — Lokalne Centrum Dowodzenia AI

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Lokalne centrum dowodzenia w stylu JARVIS/FRIDAY — CustomTkinter, Ollama, Agent ReAct.

```
PC (Windows + RTX)
├── Ollama (localhost:11434)
├── mobius_gui.py — streaming, głos, agent
└── Wszystko lokalnie
```

**GitHub:** [github.com/pontonempopokojuXD/mobius](https://github.com/pontonempopokojuXD/mobius)

---

## File Structure

```
mobius/
├── mobius_gui.py                 # GUI — centrum dowodzenia (Ollama)
├── mobius_agent.py               # Agent ReAct — narzędzia (pliki, RAG, shell)
├── mobius_voice.py               # STT (mikrofon) + TTS (edge-tts)
├── mobius_rag.py                 # Baza wiedzy (ChromaDB)
├── mobius_reminders.py           # Przypomnienia
├── mobius_config.json            # Konfiguracja GUI
├── requirements_gui.txt          # Zależności GUI
├── MOBIUS_ROADMAP.md             # Roadmap do JARVIS/FRIDAY
├── DEPLOY.md                     # Przewodnik wdrożenia
├── scripts/
│   ├── setup_gui.bat             # Instalacja zależności GUI
│   ├── start_gui.bat             # Uruchom GUI
│   └── start_sentinel.sh         # Sentinel (Linux, opcjonalnie)
└── node1_linux/
    ├── sentinel_node.py          # Master: VAD + Whisper (architektura distributed)
    └── requirements.txt
```

---

## GUI — Lokalne Centrum Dowodzenia (Windows)

```powershell
pip install -r requirements_gui.txt
python mobius_gui.py
```

**Funkcje:** streaming odpowiedzi, głos (STT/TTS), tryb Agent (ReAct), backend Ollama.

| Funkcja | Opis |
|---------|------|
| **Streaming** | Odpowiedzi token po tokenie |
| **Głos** | Mikrofon (STT) + Odtwarzanie (TTS, edge-tts) |
| **Agent** | ReAct + narzędzia: pliki, RAG, przypomnienia, shell |
| **Backend** | Ollama |

**Wymaga:** Ollama na `http://localhost:11434`.

### Narzędzia agenta

| Narzędzie | Opis |
|-----------|------|
| `read_file`, `write_file`, `list_dir` | Pliki |
| `add_reminder(text, when)` | Przypomnienia |
| `rag_search(query)`, `rag_add(text)`, `rag_add_file(path)` | Baza wiedzy |
| `run_shell(command)` | PowerShell (wymaga włączenia w config) |

---

## n8n / HTTP API

```bash
pip install flask
python mobius_api.py --port 5000
```

| Endpoint | Method | Opis |
|----------|--------|------|
| `/ask` | POST | Pojedyncze pytanie do LLM |
| `/agent` | POST | ReAct agent z narzędziami |
| `/reminder` | POST | Dodaj przypomnienie |
| `/reminders` | GET | Lista przypomnień |
| `/rag/add` | POST | Dodaj do bazy wiedzy |
| `/rag/search` | POST | Wyszukaj w bazie wiedzy |
| `/task` | POST | Uruchom zadanie w tle |
| `/task/<id>` | GET | Status zadania |
| `/status` | GET | Status systemu |

### Integracja z n8n

**Uruchomienie API (na PC z MOBIUS):**
```bash
python mobius_api.py --port 5000 --host 0.0.0.0
```

**Adres:** `http://localhost:5000` (lokalnie) lub `http://192.168.1.249:5000` (z innego urządzenia w sieci).

**Autoryzacja (opcjonalna):** Jeśli w `mobius_config.json` ustawisz `api.auth_token`, dodaj header:
```
X-MOBIUS-TOKEN: <token>
```

**Przykłady node'ów HTTP Request:**

| Endpoint | Body | Odpowiedź |
|----------|------|-----------|
| `POST /ask` | `{ "prompt": "{{ $json.text }}" }` | `response`, `elapsed_s` |
| `POST /agent` | `{ "prompt": "..." }` | `response`, `steps`, `elapsed_s` |
| `POST /reminder` | `{ "text": "...", "when": "2025-03-02 10:00" }` | `status`, `message` |
| `GET /reminders` | — | `reminders` |
| `POST /rag/add` | `{ "text": "..." }` | `status` |
| `POST /rag/search` | `{ "query": "...", "n": 5 }` | `results` |
| `GET /status` | — | `ollama`, `model`, `version` |

**Minimalny workflow n8n:**
1. Trigger (np. Webhook, Schedule)
2. HTTP Request → `POST http://192.168.1.249:5000/ask`
3. Body: `{ "prompt": "{{ $json.text }}" }`
4. Użyj `{{ $json.response }}` w kolejnych krokach

---

## Sentinel (opcjonalnie — architektura distributed)

Sentinel to Node 1 dla architektury distributed (Linux + Whisper). Wymaga Node 2 (Titan), który został usunięty z projektu. Aby przywrócić pełny stack distributed, użyj brancha `backup-with-titan`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|--------------|
| `OLLAMA_HOST` | `http://localhost:11434` | URL Ollama API |
