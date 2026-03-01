# Kontekst sprzętowy — MOBIUS

> Dokument do przekazania Claude / AI — opis aktualnej konfiguracji użytkownika.

---

## Sprzęt

### 1. PC główny (Windows)
- **GPU:** RTX (prawdopodobnie RTX 5060 Ti lub inna seria RTX)
- **OS:** Windows 10/11
- **Rola:** Główna stacja robocza — GUI MOBIUS, Ollama
- **Status:** Działa. Ollama zainstalowane, model qwen2.5:7b pobrany. GUI MOBIUS uruchamiane lokalnie.

### 2. Laptop Lenovo G570 (Linux)
- **CPU:** Intel Core i3/i5 (generacja ~2011–2012)
- **GPU:** Zintegrowana (brak dedykowanej karty)
- **OS:** Linux
- **Rola:** Potencjalny Node 1 (Sentinel) — routing, STT (Whisper na CPU)
- **Status:** Dostępny, ale słaby sprzęt — Whisper na CPU może być wolny.

---

## Aktualna konfiguracja

| Element | Wybór | Uzasadnienie |
|--------|-------|--------------|
| **Backend LLM** | **Ollama** | Prostszy setup, działa od razu, GPU RTX wykorzystywane automatycznie |
| **Model** | qwen2.5:7b | Dobry balans jakość/zasoby, polski |
| **Titan** | Usunięty | Backend Titan usunięty z projektu. Zobacz branch `backup-with-titan` aby przywrócić. |

---

## Architektura (obecna vs możliwa)

### Obecna (single-node)
```
PC (Windows + RTX)
├── Ollama (localhost:11434)
├── mobius_gui.py
└── Wszystko lokalnie
```

### Możliwa (distributed) — wymaga brancha backup-with-titan
```
Lenovo G570 (Linux)          PC (Windows + RTX)
     Sentinel  ←── gRPC ──►  Titan (usunięty z master)
  (routing, STT)             (LLM na GPU)
```

---

## Decyzje projektowe

1. **Ollama > Titan** — na jednym PC z RTX Ollama jest prostsze i wystarczające.
2. **Titan** — usunięty. Przywróć z brancha `backup-with-titan` gdy potrzebny distributed setup.
3. **Laptop G570** — może pełnić rolę Sentinela, ale CPU jest słabe; lżejsze zadania (routing, VAD) realne, Whisper może być wolny.

---

## Ostatnie zmiany (commit)

- Dynamiczne opisy narzędzi agenta (tylko dozwolone w prompt)
- Odświeżanie listy modeli Ollama przy przełączeniu backendu
- qwen2.5:7b jako domyślny model
- TODO w `get_due_reminders` (brak filtrowania po `when`)

---

## Optymalizacja VRAM (Ollama)

Przy wysokim zużyciu VRAM (~90%) możesz:

### 1. Mniejszy model
- `qwen2.5:3b` lub `llama3.2:3b` zamiast 7B
- `ollama pull qwen2.5:3b`

### 2. Kontekst (num_ctx)
- Ustawienia → Model i inferencja → **Kontekst (num_ctx)**
- Zmniejsz z 4096 do **2048** lub **1024** — KV cache zajmuje mniej VRAM

### 3. Warstwy na GPU (num_gpu)
- Ustawienia → Model i inferencja → **Warstwy na GPU (num_gpu)**
- `-1` = wszystkie warstwy na GPU (domyślne)
- Np. `20` = tylko 20 warstw na GPU, reszta na CPU — mniej VRAM, wolniejsza inferencja
- Qwen2.5 7B ma ~28 warstw; eksperymentuj z 18–24

### 4. Zmienne środowiskowe (przed uruchomieniem Ollama)
```bash
set OLLAMA_MAX_LOADED=1    # tylko jeden model w pamięci
```
Restart usługi Ollama po zmianie.

### 5. Kwantyzacja
- `qwen2.5:7b` jest już Q4_K_M
- Możesz spróbować `qwen2.5:7b-instruct-q4_0` (jeśli dostępny) — mniejszy rozmiar

---

*Wygenerowano: 2025-02-28*
