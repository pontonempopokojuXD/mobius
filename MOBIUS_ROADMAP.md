# MOBIUS — Roadmap do JARVIS/FRIDAY

Cel: autonomiczny AGI w stylu asystentów z uniwersum Marvel.

---

## Zaimplementowane ✅

| Funkcja | Status | Plik |
|---------|--------|------|
| Streaming odpowiedzi | ✅ | mobius_gui.py |
| Głos — STT (mikrofon) | ✅ | mobius_voice.py, mobius_gui.py |
| Głos — TTS (odtwarzanie) | ✅ | mobius_voice.py |
| Agent ReAct + narzędzia | ✅ | mobius_agent.py |
| Tryb Agent (checkbox) | ✅ | mobius_gui.py |

### Narzędzia agenta
- `read_file(path)` — odczyt pliku
- `write_file(path, content)` — zapis pliku
- `list_dir(path)` — listowanie katalogu
- `run_shell(command)` — PowerShell
- `execute_script(name, *args)` — skrypty Python z mobius

---

## Do zrobienia

### Faza 2 — Proaktywność ✅
- [x] Monitorowanie sprzętu — alerty (CPU, RAM, temp GPU)
- [x] Przypomnienia (add_reminder, wyświetlanie przy starcie)
- [ ] Automatyczne podsumowania sesji

### Faza 3 — Pamięć rozszerzona ✅
- [x] RAG — baza wiedzy (ChromaDB)
- [ ] Embeddingi — semantyczne wyszukiwanie
- [ ] Hierarchia pamięci (krótko/długoterminowa)

### Faza 4 — Multi-modal
- [ ] Wizja — screenshot, kamera (LLaVA / GPT-4V)
- [ ] Obrazy w czacie
- [ ] Dokumenty (PDF, DOCX)

### Faza 5 — Integracja systemu
- [ ] Windows — powiadomienia, schowek
- [ ] Wake word ("Mobius")
- [ ] Always-on listening (opcjonalnie)

### Faza 6 — Architektura
- [ ] Plugin system
- [ ] Hooks (pre/post response)
- [ ] Zewnętrzne API

---

## Zależności głosowe

```bash
# TTS (edge-tts — Microsoft, darmowy)
pip install edge-tts

# STT (SpeechRecognition + mikrofon)
pip install SpeechRecognition PyAudio
# Windows: PyAudio może wymagać pip install pipwin && pipwin install pyaudio
```

---

## Użycie agenta

1. Zaznacz checkbox **Agent** w GUI
2. Zadaj pytanie wymagające działania, np.:
   - "Wylistuj pliki w folderze mobius"
   - "Przeczytaj README.md i podsumuj"
   - "Zapisz do test.txt tekst: Hello Mobius"
   - "Uruchom polecenie: dir"

Agent używa formatu ReAct: Thought → Action → Observation → Final Answer.
