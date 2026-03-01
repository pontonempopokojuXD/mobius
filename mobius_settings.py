"""
MOBIUS — Panel ustawień AGI
Rozbudowana konfiguracja dla JARVIS/FRIDAY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk

CONFIG_FILE = Path(__file__).resolve().parent / "mobius_config.json"

# Wszystkie dostępne narzędzia agenta
ALL_TOOLS = [
    "read_file", "write_file", "list_dir",
    "add_reminder", "rag_search", "rag_add", "rag_add_file",
    "run_shell", "execute_script",
    "web_search", "take_screenshot",
    "add_background_task", "get_task_status",
    "get_active_window", "get_clipboard", "set_clipboard",
]


def _load_raw_config() -> dict:
    """Wczytaj surowy config JSON."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    """Zapisz config do JSON."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class SettingsDialog(ctk.CTkToplevel):
    """Okno ustawień AGI z zakładkami."""

    def __init__(self, parent: ctk.CTk, colors: dict, on_save: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.colors = colors
        self.on_save = on_save
        self.raw = _load_raw_config()

        self.title("MOBIUS — Ustawienia AGI")
        self.geometry("700x580")
        self.minsize(600, 500)

        self.configure(fg_color=colors["bg"])
        self._build_ui()

    def _get(self, section: str, key: str, default: Any) -> Any:
        return self.raw.get(section, {}).get(key, default)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self, fg_color=self.colors["bg_card"])
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.tabview.grid_columnconfigure(0, weight=1)

        self._tab_model()
        self._tab_memory()
        self._tab_agent()
        self._tab_voice()
        self._tab_notifications()
        self._tab_hardware()
        self._tab_connections()
        self._tab_persona()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Zapisz",
            width=120,
            fg_color=self.colors["accent_dim"],
            hover_color=self.colors["accent"],
            command=self._save,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_frame,
            text="Anuluj",
            width=120,
            fg_color=self.colors["bg_card"],
            command=self.destroy,
        ).pack(side="right")

    def _section(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        lbl = ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(weight="bold"), text_color=self.colors["accent"])
        lbl.pack(anchor="w", pady=(12, 4))
        return parent

    def _row(self, parent: ctk.CTkFrame, label: str) -> ctk.CTkFrame:
        """Zwraca ramkę (grid) — dodaj widget do niej: w.grid(row=0, column=1, sticky='ew')."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=4)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text=label, width=180, anchor="w", text_color=self.colors["text_dim"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        return f

    def _tab_model(self) -> None:
        tab = self.tabview.add("Model")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "Parametry inferencji")
        self.temp_var = ctk.DoubleVar(value=float(self._get("inference", "temperature", 0.7)))
        r = self._row(tab, "Temperature (0–2):")
        ctk.CTkSlider(r, from_=0, to=2, variable=self.temp_var, width=200).grid(row=0, column=1, sticky="ew")

        self.top_p_var = ctk.DoubleVar(value=float(self._get("inference", "top_p", 0.9)))
        r = self._row(tab, "Top-p:")
        ctk.CTkSlider(r, from_=0, to=1, variable=self.top_p_var, width=200).grid(row=0, column=1, sticky="ew")

        self.max_tokens_var = ctk.IntVar(value=int(self._get("inference", "max_new_tokens", 512)))
        r = self._row(tab, "Max tokenów:")
        ctk.CTkEntry(r, textvariable=self.max_tokens_var, width=100).grid(row=0, column=1, sticky="ew")

    def _tab_memory(self) -> None:
        tab = self.tabview.add("Pamięć")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "Kontekst rozmowy")
        self.max_context_var = ctk.IntVar(value=int(self._get("gui", "max_context_messages", 12)))
        r = self._row(tab, "Wiadomości w kontekście:")
        ctk.CTkEntry(r, textvariable=self.max_context_var, width=100).grid(row=0, column=1, sticky="ew")

        self.max_stored_var = ctk.IntVar(value=int(self._get("memory", "max_messages_stored", 500)))
        r = self._row(tab, "Max zapisanych wiadomości:")
        ctk.CTkEntry(r, textvariable=self.max_stored_var, width=100).grid(row=0, column=1, sticky="ew")

        self.auto_save_var = ctk.IntVar(value=int(self._get("memory", "auto_save_interval_seconds", 30)))
        r = self._row(tab, "Auto-zapis (sekundy):")
        ctk.CTkEntry(r, textvariable=self.auto_save_var, width=100).grid(row=0, column=1, sticky="ew")

        self._section(tab, "RAG")
        self.rag_n_var = ctk.IntVar(value=int(self._get("rag", "n_results", 5)))
        r = self._row(tab, "Wyników wyszukiwania:")
        ctk.CTkEntry(r, textvariable=self.rag_n_var, width=100).grid(row=0, column=1, sticky="ew")

    def _tab_agent(self) -> None:
        tab = self.tabview.add("Agent")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "ReAct loop")
        self.max_steps_var = ctk.IntVar(value=int(self._get("agent", "max_steps", 5)))
        r = self._row(tab, "Max kroków:")
        ctk.CTkEntry(r, textvariable=self.max_steps_var, width=100).grid(row=0, column=1, sticky="ew")

        self._section(tab, "Narzędzia (zaznacz dozwolone)")
        allowed = set(self._get("agent", "allowed_tools", ["read_file", "write_file", "list_dir", "add_reminder", "rag_search", "rag_add", "rag_add_file"]))
        self.tool_vars: dict[str, ctk.BooleanVar] = {}
        for t in ALL_TOOLS:
            v = ctk.BooleanVar(value=t in allowed)
            self.tool_vars[t] = v
            cb = ctk.CTkCheckBox(tab, text=t, variable=v, width=180)
            cb.pack(anchor="w", padx=20, pady=2)

    def _tab_voice(self) -> None:
        tab = self.tabview.add("Głos")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "TTS (edge-tts)")
        voices = ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural", "en-US-JennyNeural", "en-GB-SoniaNeural"]
        self.tts_voice_var = ctk.StringVar(value=self._get("voice", "tts_voice", "pl-PL-ZofiaNeural"))
        r = self._row(tab, "Głos:")
        ctk.CTkOptionMenu(r, values=voices, variable=self.tts_voice_var, width=200).grid(row=0, column=1, sticky="ew")

        self._section(tab, "STT")
        self.stt_lang_var = ctk.StringVar(value=self._get("voice", "stt_language", "pl-PL"))
        r = self._row(tab, "Język:")
        ctk.CTkOptionMenu(r, values=["pl-PL", "en-US", "en-GB"], variable=self.stt_lang_var, width=150).grid(row=0, column=1, sticky="ew")

    def _tab_notifications(self) -> None:
        tab = self.tabview.add("Powiadomienia")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "Toast Windows")
        self.notify_on_response_var = ctk.BooleanVar(value=self._get("notifications", "on_response", True))
        ctk.CTkCheckBox(tab, text="Powiadomienie po odpowiedzi", variable=self.notify_on_response_var).pack(anchor="w", padx=20, pady=4)
        self.notify_on_agent_var = ctk.BooleanVar(value=self._get("notifications", "on_agent", True))
        ctk.CTkCheckBox(tab, text="Powiadomienie po zakończeniu agenta", variable=self.notify_on_agent_var).pack(anchor="w", padx=20, pady=4)

    def _tab_hardware(self) -> None:
        tab = self.tabview.add("Sprzęt")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "Progi alertów (%)")
        self.cpu_alert_var = ctk.IntVar(value=int(self._get("alerts", "cpu_threshold_percent", 90)))
        r = self._row(tab, "CPU:")
        ctk.CTkEntry(r, textvariable=self.cpu_alert_var, width=80).grid(row=0, column=1, sticky="ew")
        self.ram_alert_var = ctk.IntVar(value=int(self._get("alerts", "ram_threshold_percent", 95)))
        r = self._row(tab, "RAM:")
        ctk.CTkEntry(r, textvariable=self.ram_alert_var, width=80).grid(row=0, column=1, sticky="ew")
        self.gpu_temp_var = ctk.IntVar(value=int(self._get("alerts", "gpu_temp_threshold_c", 85)))
        r = self._row(tab, "GPU temp (°C):")
        ctk.CTkEntry(r, textvariable=self.gpu_temp_var, width=80).grid(row=0, column=1, sticky="ew")

        self._section(tab, "Odświeżanie")
        self.hw_refresh_var = ctk.IntVar(value=int(self._get("gui", "hardware_refresh_interval_ms", 2000)))
        r = self._row(tab, "Monitor sprzętu (ms):")
        ctk.CTkEntry(r, textvariable=self.hw_refresh_var, width=100).grid(row=0, column=1, sticky="ew")
        self.conn_refresh_var = ctk.IntVar(value=int(self._get("gui", "connection_check_interval_ms", 10000)))
        r = self._row(tab, "Sprawdzenie połączenia (ms):")
        ctk.CTkEntry(r, textvariable=self.conn_refresh_var, width=100).grid(row=0, column=1, sticky="ew")

    def _tab_connections(self) -> None:
        tab = self.tabview.add("Połączenia")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "Ollama")
        self.ollama_host_var = ctk.StringVar(value=self._get("ollama", "host", "http://localhost:11434"))
        r = self._row(tab, "URL:")
        ctk.CTkEntry(r, textvariable=self.ollama_host_var, width=280).grid(row=0, column=1, sticky="ew")
        self.ollama_timeout_var = ctk.IntVar(value=int(self._get("ollama", "timeout_seconds", 90)))
        r = self._row(tab, "Timeout (s):")
        ctk.CTkEntry(r, textvariable=self.ollama_timeout_var, width=80).grid(row=0, column=1, sticky="ew")

        self._section(tab, "Titan")
        self.titan_host_var = ctk.StringVar(value=self._get("titan", "host", "localhost"))
        r = self._row(tab, "Host:")
        ctk.CTkEntry(r, textvariable=self.titan_host_var, width=150).grid(row=0, column=1, sticky="ew")
        self.titan_port_var = ctk.IntVar(value=int(self._get("titan", "port", 50051)))
        r = self._row(tab, "Port:")
        ctk.CTkEntry(r, textvariable=self.titan_port_var, width=80).grid(row=0, column=1, sticky="ew")
        self.titan_timeout_var = ctk.IntVar(value=int(self._get("titan", "timeout_seconds", 300)))
        r = self._row(tab, "Timeout (s):")
        ctk.CTkEntry(r, textvariable=self.titan_timeout_var, width=80).grid(row=0, column=1, sticky="ew")

    def _tab_persona(self) -> None:
        tab = self.tabview.add("Persona")
        tab.grid_columnconfigure(0, weight=1)

        self._section(tab, "System prompt (nadpisuje domyślny)")
        self.system_prompt_tb = ctk.CTkTextbox(tab, height=120, fg_color=self.colors["bg_card"])
        self.system_prompt_tb.pack(fill="x", pady=4)
        self.system_prompt_tb.insert("1.0", self._get("persona", "system_prompt_override", ""))
        ctk.CTkLabel(tab, text="Puste = domyślny Pontifex Rex", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=10)).pack(anchor="w")

    def _save(self) -> None:
        data = _load_raw_config()

        data.setdefault("inference", {})["temperature"] = self.temp_var.get()
        data.setdefault("inference", {})["top_p"] = self.top_p_var.get()
        data.setdefault("inference", {})["max_new_tokens"] = self.max_tokens_var.get()

        data.setdefault("gui", {})["max_context_messages"] = self.max_context_var.get()
        data.setdefault("memory", {})["max_messages_stored"] = self.max_stored_var.get()
        data.setdefault("memory", {})["auto_save_interval_seconds"] = self.auto_save_var.get()
        data.setdefault("rag", {})["n_results"] = self.rag_n_var.get()

        data.setdefault("agent", {})["max_steps"] = self.max_steps_var.get()
        data.setdefault("agent", {})["allowed_tools"] = [t for t in ALL_TOOLS if self.tool_vars[t].get()]

        data.setdefault("voice", {})["tts_voice"] = self.tts_voice_var.get()
        data.setdefault("voice", {})["stt_language"] = self.stt_lang_var.get()

        data.setdefault("notifications", {})["on_response"] = self.notify_on_response_var.get()
        data.setdefault("notifications", {})["on_agent"] = self.notify_on_agent_var.get()

        data.setdefault("alerts", {})["cpu_threshold_percent"] = self.cpu_alert_var.get()
        data.setdefault("alerts", {})["ram_threshold_percent"] = self.ram_alert_var.get()
        data.setdefault("alerts", {})["gpu_temp_threshold_c"] = self.gpu_temp_var.get()
        data.setdefault("gui", {})["hardware_refresh_interval_ms"] = self.hw_refresh_var.get()
        data.setdefault("gui", {})["connection_check_interval_ms"] = self.conn_refresh_var.get()

        data.setdefault("ollama", {})["host"] = self.ollama_host_var.get().rstrip("/")
        data.setdefault("ollama", {})["timeout_seconds"] = self.ollama_timeout_var.get()
        data.setdefault("titan", {})["host"] = self.titan_host_var.get()
        data.setdefault("titan", {})["port"] = self.titan_port_var.get()
        data.setdefault("titan", {})["timeout_seconds"] = self.titan_timeout_var.get()

        sp = self.system_prompt_tb.get("1.0", "end").strip()
        if sp:
            data.setdefault("persona", {})["system_prompt_override"] = sp
        elif "persona" in data:
            data["persona"].pop("system_prompt_override", None)

        _save_config(data)
        if self.on_save:
            self.on_save()
        self.destroy()
