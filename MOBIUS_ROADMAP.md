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
- `read_file`, `write_file`, `list_dir` — pliki
- `add_reminder(text, when)` — przypomnienia
- `rag_search`, `rag_add`, `rag_add_file` — baza wiedzy
- `run_shell`, `execute_script` — wymagają włączenia w `agent.allowed_tools` (bezpieczeństwo)

---

## Do zrobienia

### Faza 2 — Proaktywność ✅
- [x] Monitorowanie sprzętu — alerty (CPU, RAM, temp GPU)
- [x] Przypomnienia (add_reminder, wyświetlanie przy starcie)
- [x] **Autonomiczny cykl AGI** — Percepcja → Myślenie → Działanie → Uczenie się (mobius_autonomous.py)
- [x] **Proaktywne powiadomienia** — Za 15 min przed przypomnieniem: LLM generuje pytanie, toast + log
- [ ] Automatyczne podsumowania sesji

### Faza 3 — Pamięć rozszerzona ✅
- [x] RAG — baza wiedzy (ChromaDB)
- [x] agent.allowed_tools — run_shell wyłączony domyślnie
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
