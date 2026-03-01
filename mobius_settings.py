"""
MOBIUS — Panel ustawień
Pełna konfiguracja AGI z opisami i walidacją.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk

CONFIG_FILE = Path(__file__).resolve().parent / "mobius_config.json"

ALL_TOOLS = [
    "read_file", "write_file", "list_dir",
    "add_reminder", "rag_search", "rag_add", "rag_add_file",
    "run_shell", "execute_script",
    "web_search", "take_screenshot",
    "add_background_task", "get_task_status",
    "get_active_window", "get_clipboard", "set_clipboard",
]

TOOL_DESCRIPTIONS: dict[str, str] = {
    "read_file": "Odczyt plików",
    "write_file": "Zapis do plików",
    "list_dir": "Listowanie katalogów",
    "add_reminder": "Przypomnienia",
    "rag_search": "Wyszukiwanie w bazie wiedzy",
    "rag_add": "Dodawanie do RAG",
    "rag_add_file": "Indeksowanie plików do RAG",
    "run_shell": "Polecenia PowerShell (wymaga wlaczenia)",
    "execute_script": "Uruchamianie skryptow Python",
    "web_search": "Wyszukiwanie w internecie",
    "take_screenshot": "Zrzut ekranu + analiza",
    "add_background_task": "Zadania w tle",
    "get_task_status": "Status zadan",
    "get_active_window": "Aktywne okno",
    "get_clipboard": "Schowek (odczyt)",
    "set_clipboard": "Schowek (zapis)",
}


def _load_raw_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _defaults() -> dict:
    """Wartosci domyslne dla przycisku Reset."""
    return {
        "inference": {"temperature": 0.7, "top_p": 0.9, "max_new_tokens": 512, "num_ctx": 2048, "num_gpu": 20},
        "gui": {"max_context_messages": 12, "hardware_refresh_interval_ms": 2000, "connection_check_interval_ms": 10000},
        "memory": {"max_messages_stored": 500, "auto_save_interval_seconds": 30, "auto_index_on_close": True, "recall_n_results": 3},
        "rag": {"n_results": 5},
        "agent": {"max_steps": 5, "allowed_tools": ["read_file", "write_file", "list_dir", "add_reminder", "rag_search", "rag_add", "rag_add_file", "web_search"]},
        "voice": {"tts_voice": "pl-PL-ZofiaNeural", "stt_language": "pl-PL"},
        "notifications": {"on_response": True, "on_agent": True},
        "alerts": {"cpu_threshold_percent": 90, "ram_threshold_percent": 95, "gpu_temp_threshold_c": 85},
        "ollama": {"host": "http://localhost:11434", "timeout_seconds": 90, "fetch_models_from_api": True},
        "daemon": {"enabled": True, "check_interval_seconds": 60, "cpu_sustained_checks": 3, "autonomous_enabled": True, "autonomous_interval_seconds": 300, "proactive_enabled": True},
        "profile": {"auto_update": True},
        "agent_system_context": False,
        "wakeword_vad_threshold": 0.01,
        "api": {"enabled": False, "host": "0.0.0.0", "port": 5000, "auth_token": ""},
    }


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, colors: dict, on_save: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.colors = colors or {}
        self.on_save = on_save
        self.raw = _load_raw_config()

        self.title("MOBIUS — Ustawienia")
        self.geometry("920x720")
        self.minsize(800, 600)

        self.configure(fg_color=colors.get("bg", "#0a0a0c"))
        self.transient(parent)
        self._build_ui()

    def _get(self, section: str, key: str, default: Any) -> Any:
        if section in self.raw and isinstance(self.raw[section], dict):
            return self.raw[section].get(key, default)
        if section == "agent_system_context" or (section == "" and key == ""):
            return self.raw.get("agent_system_context", default)
        if section == "wakeword_vad_threshold":
            return self.raw.get("wakeword_vad_threshold", default)
        return default

    def _card(self, parent: ctk.CTkFrame, title: str, desc: str = "") -> ctk.CTkFrame:
        """Karta sekcji z tytulem i opcjonalnym opisem."""
        card = ctk.CTkFrame(parent, fg_color=self.colors.get("bg_card", "#1a1a24"), corner_radius=8, border_width=1, border_color=self.colors.get("border", "#2a2a35"))
        card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold", size=13), text_color=self.colors.get("accent", "#00d4aa")).grid(row=0, column=0, sticky="w")
        if desc:
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10), text_color=self.colors.get("text_dim", "#6b6b7a"), anchor="w", justify="left").grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        return card

    def _row(self, parent: ctk.CTkFrame, label: str, hint: str = "", start_row: int = 0) -> tuple[ctk.CTkFrame, int]:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text=label, width=220, anchor="w", text_color=self.colors.get("text_dim", "#6b6b7a"), font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 12))
        return f, start_row

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)

        # ─── Model / Inferencja ───
        card = self._card(main, "Model i inferencja", "Parametry LLM: kreatywnosc, dlugosc odpowiedzi.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.temp_var = ctk.DoubleVar(value=float(self._get("inference", "temperature", 0.7)))
        r = self._row(card, "Temperature (0–2):", "Kreatywnosc. 0 = deterministycznie, 2 = bardzo losowo.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkSlider(r, from_=0, to=2, variable=self.temp_var, width=200).grid(row=0, column=1, sticky="ew")
        row += 1
        self.top_p_var = ctk.DoubleVar(value=float(self._get("inference", "top_p", 0.9)))
        r = self._row(card, "Top-p (nucleus):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkSlider(r, from_=0, to=1, variable=self.top_p_var, width=180).grid(row=0, column=1, sticky="ew")
        row += 1
        self.max_tokens_var = ctk.IntVar(value=int(self._get("inference", "max_new_tokens", 512)))
        r = self._row(card, "Max tokenow:", "Maksymalna dlugosc odpowiedzi.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.max_tokens_var, width=100).grid(row=0, column=1, sticky="w")
        row += 1
        self.num_ctx_var = ctk.IntVar(value=int(self._get("inference", "num_ctx", 4096)))
        r = self._row(card, "Kontekst (num_ctx):", "Okno kontekstu w tokenach. Mniejsze = mniej VRAM (np. 2048).", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.num_ctx_var, width=100).grid(row=0, column=1, sticky="w")
        row += 1
        self.num_gpu_var = ctk.IntVar(value=int(self._get("inference", "num_gpu", -1)))
        r = self._row(card, "Warstwy na GPU (num_gpu):", "-1 = wszystkie. Nizsza wartosc = mniej VRAM, wolniejsza inferencja.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.num_gpu_var, width=100).grid(row=0, column=1, sticky="w")

        # ─── Pamiec ───
        card = self._card(main, "Pamiec", "Kontekst rozmowy, RAG, indeksowanie sesji.")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.max_context_var = ctk.IntVar(value=int(self._get("gui", "max_context_messages", 12)))
        r = self._row(card, "Wiadomosci w kontekscie:", "Ile ostatnich wiadomosci wysylac do LLM.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.max_context_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.max_stored_var = ctk.IntVar(value=int(self._get("memory", "max_messages_stored", 500)))
        r = self._row(card, "Max zapisanych:", "Limit w memory.json.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.max_stored_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.auto_save_var = ctk.IntVar(value=int(self._get("memory", "auto_save_interval_seconds", 30)))
        r = self._row(card, "Auto-zapis (s):", "Co ile sekund zapisywac.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.auto_save_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.memory_auto_index_var = ctk.BooleanVar(value=self._get("memory", "auto_index_on_close", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        r.grid_columnconfigure(0, weight=1)
        ctk.CTkCheckBox(r, text="Indeksuj sesje do RAG przy zamknieciu", variable=self.memory_auto_index_var).grid(row=0, column=0, sticky="w")
        row += 1
        self.recall_n_var = ctk.IntVar(value=int(self._get("memory", "recall_n_results", 3)))
        r = self._row(card, "Recall (wynikow RAG):", "Ile fragmentow z pamieci dodawac do promptu.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.recall_n_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.rag_n_var = ctk.IntVar(value=int(self._get("rag", "n_results", 5)))
        r = self._row(card, "RAG — wynikow wyszukiwania:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.rag_n_var, width=80).grid(row=0, column=1, sticky="w")

        # ─── Agent ───
        card = self._card(main, "Agent ReAct", "Narzedzia i limit krokow petli.")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.max_steps_var = ctk.IntVar(value=int(self._get("agent", "max_steps", 5)))
        r = self._row(card, "Max krokow:", "Limit iteracji Thought->Action->Observation.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.max_steps_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.agent_system_context_var = ctk.BooleanVar(value=self.raw.get("agent_system_context", False))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        r.grid_columnconfigure(0, weight=1)
        ctk.CTkCheckBox(r, text="Dodawaj kontekst systemowy (aktywne okno, aplikacje)", variable=self.agent_system_context_var).grid(row=0, column=0, sticky="w")
        row += 1
        self._section_tools(card, row)

        # ─── Glos ───
        card = self._card(main, "Glos (TTS / STT)", "Edge-TTS i rozpoznawanie mowy.")
        card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        row = 2
        voices = ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural", "en-US-JennyNeural", "en-GB-SoniaNeural", "en-US-GuyNeural"]
        self.tts_voice_var = ctk.StringVar(value=self._get("voice", "tts_voice", "pl-PL-ZofiaNeural"))
        r = self._row(card, "Glos TTS:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkOptionMenu(r, values=voices, variable=self.tts_voice_var, width=200).grid(row=0, column=1, sticky="w")
        row += 1
        self.stt_lang_var = ctk.StringVar(value=self._get("voice", "stt_language", "pl-PL"))
        r = self._row(card, "Jezyk STT:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkOptionMenu(r, values=["pl-PL", "en-US", "en-GB"], variable=self.stt_lang_var, width=150).grid(row=0, column=1, sticky="w")
        row += 1
        self.wakeword_vad_var = ctk.DoubleVar(value=float(self.raw.get("wakeword_vad_threshold", 0.01)))
        r = self._row(card, "Wake word — prog VAD:", "Czulosc wykrywania (0.01 = niska).", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.wakeword_vad_var, width=80).grid(row=0, column=1, sticky="w")

        # ─── Powiadomienia ───
        card = self._card(main, "Powiadomienia", "Toast Windows po odpowiedzi i agencie.")
        card.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.notify_on_response_var = ctk.BooleanVar(value=self._get("notifications", "on_response", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Po odpowiedzi", variable=self.notify_on_response_var).grid(row=0, column=0, sticky="w")
        row += 1
        self.notify_on_agent_var = ctk.BooleanVar(value=self._get("notifications", "on_agent", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Po zakonczeniu agenta", variable=self.notify_on_agent_var).grid(row=0, column=0, sticky="w")

        # ─── Sprzet i alerty ───
        card = self._card(main, "Sprzet i alerty", "Progi CPU/RAM/GPU oraz interwaly odswiezania.")
        card.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.cpu_alert_var = ctk.IntVar(value=int(self._get("alerts", "cpu_threshold_percent", 90)))
        r = self._row(card, "CPU alert (%):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.cpu_alert_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.ram_alert_var = ctk.IntVar(value=int(self._get("alerts", "ram_threshold_percent", 95)))
        r = self._row(card, "RAM alert (%):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.ram_alert_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.gpu_temp_var = ctk.IntVar(value=int(self._get("alerts", "gpu_temp_threshold_c", 85)))
        r = self._row(card, "GPU temp alert (C):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.gpu_temp_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.hw_refresh_var = ctk.IntVar(value=int(self._get("gui", "hardware_refresh_interval_ms", 2000)))
        r = self._row(card, "Odswiezanie monitora (ms):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.hw_refresh_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.conn_refresh_var = ctk.IntVar(value=int(self._get("gui", "connection_check_interval_ms", 10000)))
        r = self._row(card, "Sprawdzenie Ollama (ms):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.conn_refresh_var, width=80).grid(row=0, column=1, sticky="w")

        # ─── Daemon / AGI ───
        card = self._card(main, "Daemon i cykl AGI", "Monitorowanie, autonomiczny cykl, proaktywnosc.")
        card.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.daemon_enabled_var = ctk.BooleanVar(value=self._get("daemon", "enabled", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Wlacz daemon (przypomnienia, alerty)", variable=self.daemon_enabled_var).grid(row=0, column=0, sticky="w")
        row += 1
        self.daemon_interval_var = ctk.IntVar(value=int(self._get("daemon", "check_interval_seconds", 60)))
        r = self._row(card, "Interwal daemona (s):", "Co ile sekund sprawdzac.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.daemon_interval_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.daemon_cpu_checks_var = ctk.IntVar(value=int(self._get("daemon", "cpu_sustained_checks", 3)))
        r = self._row(card, "CPU sustained checks:", "Ile probek z rzedu przed alertem.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.daemon_cpu_checks_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.autonomous_enabled_var = ctk.BooleanVar(value=self._get("daemon", "autonomous_enabled", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Autonomiczny cykl AGI (Percepcja->Myslenie->Dzialanie)", variable=self.autonomous_enabled_var).grid(row=0, column=0, sticky="w")
        row += 1
        self.autonomous_interval_var = ctk.IntVar(value=int(self._get("daemon", "autonomous_interval_seconds", 300)))
        r = self._row(card, "Interwal autonomiczny (s):", "Co ile sekund cykl AGI.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.autonomous_interval_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.proactive_enabled_var = ctk.BooleanVar(value=self._get("daemon", "proactive_enabled", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Proaktywne powiadomienia (15 min przed przypomnieniem)", variable=self.proactive_enabled_var).grid(row=0, column=0, sticky="w")

        # ─── Polaczenia ───
        card = self._card(main, "Ollama", "URL i timeout API.")
        card.grid(row=7, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.ollama_host_var = ctk.StringVar(value=self._get("ollama", "host", "http://localhost:11434"))
        r = self._row(card, "URL:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.ollama_host_var, width=300).grid(row=0, column=1, sticky="ew")
        row += 1
        self.ollama_timeout_var = ctk.IntVar(value=int(self._get("ollama", "timeout_seconds", 90)))
        r = self._row(card, "Timeout (s):", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.ollama_timeout_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.fetch_models_var = ctk.BooleanVar(value=self._get("ollama", "fetch_models_from_api", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Pobieraj liste modeli z API przy starcie", variable=self.fetch_models_var).grid(row=0, column=0, sticky="w")

        # ─── API (n8n) ───
        card = self._card(main, "HTTP API (n8n)", "Flask API do integracji z n8n i innymi narzedziami.")
        card.grid(row=8, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.api_enabled_var = ctk.BooleanVar(value=self._get("api", "enabled", False))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Wlacz HTTP API", variable=self.api_enabled_var).grid(row=0, column=0, sticky="w")
        row += 1
        self.api_host_var = ctk.StringVar(value=self._get("api", "host", "0.0.0.0"))
        r = self._row(card, "Host:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.api_host_var, width=150).grid(row=0, column=1, sticky="w")
        row += 1
        self.api_port_var = ctk.IntVar(value=int(self._get("api", "port", 5000)))
        r = self._row(card, "Port:", "", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.api_port_var, width=80).grid(row=0, column=1, sticky="w")
        row += 1
        self.api_token_var = ctk.StringVar(value=self._get("api", "auth_token", ""))
        r = self._row(card, "Token (X-MOBIUS-TOKEN):", "Opcjonalna autoryzacja.", row)[0]
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkEntry(r, textvariable=self.api_token_var, width=200, show="*").grid(row=0, column=1, sticky="ew")

        # ─── Profil ───
        card = self._card(main, "Profil uzytkownika", "Auto-aktualizacja z odpowiedzi.")
        card.grid(row=9, column=0, sticky="ew", pady=(0, 12))
        row = 2
        self.profile_auto_update_var = ctk.BooleanVar(value=self._get("profile", "auto_update", True))
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkCheckBox(r, text="Aktualizuj profil z odpowiedzi MOBIUS", variable=self.profile_auto_update_var).grid(row=0, column=0, sticky="w")

        # ─── Persona ───
        card = self._card(main, "Persona (system prompt)", "Nadpisuje domyslna osobowosc JARVIS/FRIDAY.")
        card.grid(row=10, column=0, sticky="ew", pady=(0, 12))
        self.system_prompt_tb = ctk.CTkTextbox(card, height=140, fg_color=self.colors.get("bg_card", "#1a1a24"), font=ctk.CTkFont(size=11))
        self.system_prompt_tb.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        self.system_prompt_tb.insert("1.0", self._get("persona", "system_prompt_override", ""))
        ctk.CTkLabel(card, text="Puste = domyslny MOBIUS (JARVIS/FRIDAY)", text_color=self.colors.get("text_dim", "#6b6b7a"), font=ctk.CTkFont(size=10)).grid(row=3, column=0, sticky="w", padx=16, pady=(0, 12))

        # Przyciski
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        btn_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(btn_frame, text="Reset do domyslnych", width=140, fg_color=self.colors.get("bg_card", "#1a1a24"), command=self._reset_defaults).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Anuluj", width=100, fg_color=self.colors.get("bg_card", "#1a1a24"), command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(btn_frame, text="Zapisz", width=120, fg_color=self.colors.get("accent_dim", "#00a884"), hover_color=self.colors.get("accent", "#00d4aa"), command=self._save).pack(side="right")

    def _section_tools(self, card: ctk.CTkFrame, start_row: int) -> None:
        ctk.CTkLabel(card, text="Narzedzia agenta (zaznacz dozwolone)", font=ctk.CTkFont(weight="bold", size=11), text_color=self.colors.get("text", "#e8e8ec")).grid(row=start_row, column=0, sticky="w", padx=16, pady=(12, 4))
        allowed = set(self._get("agent", "allowed_tools", ["read_file", "write_file", "list_dir", "add_reminder", "rag_search", "rag_add", "rag_add_file"]))
        self.tool_vars: dict[str, ctk.BooleanVar] = {}
        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.grid(row=start_row + 1, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        for i, t in enumerate(ALL_TOOLS):
            v = ctk.BooleanVar(value=t in allowed)
            self.tool_vars[t] = v
            desc = TOOL_DESCRIPTIONS.get(t, t)
            cb = ctk.CTkCheckBox(frame, text=f"{t} — {desc}", variable=v, width=320)
            cb.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 16), pady=2)

    def _reset_defaults(self) -> None:
        d = _defaults()
        self.temp_var.set(d["inference"]["temperature"])
        self.top_p_var.set(d["inference"]["top_p"])
        self.max_tokens_var.set(d["inference"]["max_new_tokens"])
        self.num_ctx_var.set(d["inference"].get("num_ctx", 4096))
        self.num_gpu_var.set(d["inference"].get("num_gpu", -1))
        self.max_context_var.set(d["gui"]["max_context_messages"])
        self.max_stored_var.set(d["memory"]["max_messages_stored"])
        self.auto_save_var.set(d["memory"]["auto_save_interval_seconds"])
        self.memory_auto_index_var.set(d["memory"]["auto_index_on_close"])
        self.recall_n_var.set(d["memory"]["recall_n_results"])
        self.rag_n_var.set(d["rag"]["n_results"])
        self.max_steps_var.set(d["agent"]["max_steps"])
        for t, v in self.tool_vars.items():
            v.set(t in d["agent"]["allowed_tools"])
        self.agent_system_context_var.set(d["agent_system_context"])
        self.tts_voice_var.set(d["voice"]["tts_voice"])
        self.stt_lang_var.set(d["voice"]["stt_language"])
        self.wakeword_vad_var.set(d["wakeword_vad_threshold"])
        self.notify_on_response_var.set(d["notifications"]["on_response"])
        self.notify_on_agent_var.set(d["notifications"]["on_agent"])
        self.cpu_alert_var.set(d["alerts"]["cpu_threshold_percent"])
        self.ram_alert_var.set(d["alerts"]["ram_threshold_percent"])
        self.gpu_temp_var.set(d["alerts"]["gpu_temp_threshold_c"])
        self.hw_refresh_var.set(d["gui"]["hardware_refresh_interval_ms"])
        self.conn_refresh_var.set(d["gui"]["connection_check_interval_ms"])
        self.daemon_enabled_var.set(d["daemon"]["enabled"])
        self.daemon_interval_var.set(d["daemon"]["check_interval_seconds"])
        self.daemon_cpu_checks_var.set(d["daemon"]["cpu_sustained_checks"])
        self.autonomous_enabled_var.set(d["daemon"]["autonomous_enabled"])
        self.autonomous_interval_var.set(d["daemon"]["autonomous_interval_seconds"])
        self.proactive_enabled_var.set(d["daemon"]["proactive_enabled"])
        self.ollama_host_var.set(d["ollama"]["host"])
        self.ollama_timeout_var.set(d["ollama"]["timeout_seconds"])
        self.fetch_models_var.set(d["ollama"]["fetch_models_from_api"])
        self.api_enabled_var.set(d["api"]["enabled"])
        self.api_host_var.set(d["api"]["host"])
        self.api_port_var.set(d["api"]["port"])
        self.api_token_var.set(d["api"]["auth_token"])
        self.profile_auto_update_var.set(d["profile"]["auto_update"])
        self.system_prompt_tb.delete("1.0", "end")

    def _save(self) -> None:
        data = _load_raw_config()
        data.setdefault("inference", {})["temperature"] = self.temp_var.get()
        data.setdefault("inference", {})["top_p"] = self.top_p_var.get()
        data.setdefault("inference", {})["max_new_tokens"] = self.max_tokens_var.get()
        data.setdefault("inference", {})["num_ctx"] = self.num_ctx_var.get()
        data.setdefault("inference", {})["num_gpu"] = self.num_gpu_var.get()
        data.setdefault("gui", {})["max_context_messages"] = self.max_context_var.get()
        data.setdefault("memory", {})["max_messages_stored"] = self.max_stored_var.get()
        data.setdefault("memory", {})["auto_save_interval_seconds"] = self.auto_save_var.get()
        data.setdefault("memory", {})["auto_index_on_close"] = self.memory_auto_index_var.get()
        data.setdefault("memory", {})["recall_n_results"] = self.recall_n_var.get()
        data.setdefault("rag", {})["n_results"] = self.rag_n_var.get()
        data.setdefault("agent", {})["max_steps"] = self.max_steps_var.get()
        data.setdefault("agent", {})["allowed_tools"] = [t for t in ALL_TOOLS if self.tool_vars[t].get()]
        data["agent_system_context"] = self.agent_system_context_var.get()
        data.setdefault("voice", {})["tts_voice"] = self.tts_voice_var.get()
        data.setdefault("voice", {})["stt_language"] = self.stt_lang_var.get()
        data["wakeword_vad_threshold"] = self.wakeword_vad_var.get()
        data.setdefault("notifications", {})["on_response"] = self.notify_on_response_var.get()
        data.setdefault("notifications", {})["on_agent"] = self.notify_on_agent_var.get()
        data.setdefault("alerts", {})["cpu_threshold_percent"] = self.cpu_alert_var.get()
        data.setdefault("alerts", {})["ram_threshold_percent"] = self.ram_alert_var.get()
        data.setdefault("alerts", {})["gpu_temp_threshold_c"] = self.gpu_temp_var.get()
        data.setdefault("gui", {})["hardware_refresh_interval_ms"] = self.hw_refresh_var.get()
        data.setdefault("gui", {})["connection_check_interval_ms"] = self.conn_refresh_var.get()
        data.setdefault("daemon", {})["enabled"] = self.daemon_enabled_var.get()
        data.setdefault("daemon", {})["check_interval_seconds"] = self.daemon_interval_var.get()
        data.setdefault("daemon", {})["cpu_sustained_checks"] = self.daemon_cpu_checks_var.get()
        data.setdefault("daemon", {})["autonomous_enabled"] = self.autonomous_enabled_var.get()
        data.setdefault("daemon", {})["autonomous_interval_seconds"] = self.autonomous_interval_var.get()
        data.setdefault("daemon", {})["proactive_enabled"] = self.proactive_enabled_var.get()
        data.setdefault("ollama", {})["host"] = self.ollama_host_var.get().rstrip("/")
        data.setdefault("ollama", {})["timeout_seconds"] = self.ollama_timeout_var.get()
        data.setdefault("ollama", {})["fetch_models_from_api"] = self.fetch_models_var.get()
        data.setdefault("api", {})["enabled"] = self.api_enabled_var.get()
        data.setdefault("api", {})["host"] = self.api_host_var.get()
        data.setdefault("api", {})["port"] = self.api_port_var.get()
        data.setdefault("api", {})["auth_token"] = self.api_token_var.get()
        data.setdefault("profile", {})["auto_update"] = self.profile_auto_update_var.get()
        sp = self.system_prompt_tb.get("1.0", "end").strip()
        if sp:
            data.setdefault("persona", {})["system_prompt_override"] = sp
        elif "persona" in data:
            data["persona"].pop("system_prompt_override", None)
        _save_config(data)
        if self.on_save:
            self.on_save()
        self.destroy()
