# MOBIUS — Przewodnik wdrożenia na laptop serwerowy

## Szybki start (kopiowanie projektu)

```bash
# Skopiuj cały folder mobius na laptop
scp -r mobius/ user@laptop:/opt/mobius
# lub przez USB / sieć
```

---

## Scenariusze wdrożenia

### A) Tylko GUI (laptop z Ollama)

Gdy laptop ma Ollama i chcesz używać GUI jako lokalne centrum dowodzenia:

```powershell
cd C:\path\to\mobius
pip install -r requirements_gui.txt
python mobius_gui.py
# lub: scripts\start_gui.bat
```

**Wymagania:**
- Windows 10/11
- Python 3.11+
- Ollama uruchomione (`ollama serve`)
- Modele: `ollama pull llama3.2:1b` (lub inne z listy)

**Konfiguracja:** Edytuj `mobius_config.json` — host Ollama, timeout, modele.

---

### B) Pełny stack (Node 1 Linux + Node 2 Windows)

| Komponent | Maszyna | Port | Uruchomienie |
|-----------|---------|------|--------------|
| Titan (gRPC) | Windows / RTX | 50051 | `python node2_windows/titan_node.py` |
| Sentinel | Linux | — | `python node1_linux/sentinel_node.py --titan-host IP` |
| GUI | Windows | — | `python mobius_gui.py` |

**Kolejność startu:**
1. Titan (Node 2) — najpierw
2. Sentinel (Node 1) — łączy się z Titanem
3. GUI — opcjonalnie, do lokalnego czatu z Ollama

---

## Konfiguracja dla laptopa serwerowego

### 1. Zmienne środowiskowe

**Windows (Titan / GUI):**
```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
$env:TITAN_DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
```

**Linux (Sentinel):**
```bash
export TITAN_HOST=192.168.1.XXX   # IP laptopa z Titanem
export TITAN_PORT=50051
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3.2:1b
```

### 2. mobius_config.json (GUI)

```json
{
  "ollama": {
    "host": "http://localhost:11434",
    "timeout_seconds": 90,
    "fetch_models_from_api": true
  },
  "gui": {
    "max_context_messages": 12,
    "hardware_refresh_interval_ms": 2000
  }
}
```

Dla zdalnej Ollama: `"host": "http://192.168.1.XXX:11434"`

### 3. Firewall (Windows)

Jeśli Titan ma być dostępny z sieci:
```powershell
netsh advfirewall firewall add rule name="MOBIUS Titan" dir=in action=allow protocol=TCP localport=50051
```

---

## Checklist przed kopiowaniem

- [ ] `mobius_config.json` — dostosuj host Ollama
- [ ] `memory.json` — opcjonalnie wyczyść przed kopią (zawiera historię)
- [ ] `.gitignore` — upewnij się, że venv, __pycache__ nie są w repozytorium
- [ ] Wymagane pakiety: `pip install -r requirements_gui.txt` (GUI) lub odpowiedni requirements dla node

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Ollama: connection refused | Uruchom `ollama serve` |
| Brak modeli w dropdown | Kliknij "Odśwież modele" lub `ollama pull llama3.2:1b` |
| GPU: pynvml niedostępny | `pip install pynvml` |
| Titan nie startuje | Sprawdź CUDA, PyTorch, BitsAndBytes (patrz README) |
