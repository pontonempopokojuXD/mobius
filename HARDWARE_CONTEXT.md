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

*Wygenerowano: 2025-02-28*
