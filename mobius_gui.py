"""
MOBIUS GUI v2 — Centrum Dowodzenia
Prosty, zaawansowany interfejs z prawdziwymi statystykami i wykresami.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import customtkinter as ctk
import psutil
import requests

try:
    from mobius_memory import auto_index_session, recall_context, generate_session_id
    _MEMORY_AVAILABLE = True
except ImportError:
    _MEMORY_AVAILABLE = False
    def generate_session_id() -> str: return ""
    def auto_index_session(m: list, s: str) -> int: return 0
    def recall_context(q: str, n: int = 3) -> str: return ""

try:
    from mobius_profile import load_profile, save_profile, get_profile_prompt, update_profile_from_response
    _PROFILE_AVAILABLE = True
except ImportError:
    _PROFILE_AVAILABLE = False
    def load_profile() -> dict: return {"name": "", "preferences": [], "facts": [], "last_updated": ""}
    def save_profile(p: dict) -> None: pass
    def get_profile_prompt() -> str: return ""
    def update_profile_from_response(r: str, p: dict, generate_fn=None) -> dict: return p

try:
    from mobius_daemon import ProactiveDaemon
    _DAEMON_AVAILABLE = True
except ImportError:
    _DAEMON_AVAILABLE = False

try:
    from mobius_wakeword import WakeWordListener
    _WAKEWORD_AVAILABLE = True
except ImportError:
    _WAKEWORD_AVAILABLE = False
    WakeWordListener = None

try:
    from mobius_events import get_bus, HARDWARE_ALERT, REMINDER_DUE, WAKE_WORD_DETECTED, TASK_COMPLETED, AUTONOMOUS_ACTION, PROACTIVE_SUGGESTION
    _EVENTS_AVAILABLE = True
except ImportError:
    _EVENTS_AVAILABLE = False

try:
    import pynvml
    _pynvml_handle: Optional[Any] = None
    def _init_pynvml() -> bool:
        global _pynvml_handle
        if _pynvml_handle is not None: return True
        try:
            pynvml.nvmlInit()
            _pynvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            return True
        except Exception: return False
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    _pynvml_handle = None
    def _init_pynvml() -> bool: return False

MOBIUS_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = MOBIUS_ROOT / "mobius_config.json"
MEMORY_FILE = MOBIUS_ROOT / "memory.json"

DEFAULTS = {
    "ollama_host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    "ollama_timeout": 90,
    "default_models": ["qwen2.5:7b", "llama3.2:3b", "llama3.2:1b"],
    "fetch_models": True,
    "agent_allowed_tools": ["read_file", "write_file", "list_dir", "add_reminder", "rag_search", "rag_add", "rag_add_file", "web_search"],
    "agent_max_steps": 5,
    "max_context": 12,
    "hw_refresh_ms": 2000,
    "conn_check_ms": 10000,
    "cpu_alert": 90,
    "gpu_temp_alert": 85,
    "ram_alert": 95,
    "temperature": 0.7,
    "top_p": 0.9,
    "max_new_tokens": 512,
    "num_ctx": 2048,
    "num_gpu": 20,
    "notify_on_response": True,
    "notify_on_agent": True,
    "system_prompt_override": "",
    "tts_voice": "pl-PL-ZofiaNeural",
    "memory_auto_index": True,
    "memory_recall_n": 3,
    "memory_auto_save_interval": 30,
    "daemon_enabled": True,
    "daemon_interval_seconds": 60,
    "daemon_cpu_sustained_checks": 3,
    "profile_auto_update": True,
    "agent_system_context": False,
    "wakeword_vad_threshold": 0.01,
    "autonomous_enabled": True,
    "autonomous_interval_seconds": 300,
    "autonomous_allowed_tools": ["add_reminder", "rag_add", "rag_search", "read_file", "list_dir", "get_active_window", "get_clipboard"],
            "proactive_enabled": True,
    "api_enabled": False,
    "api_host": "0.0.0.0",
    "api_port": 5000,
}

MOBIUS_SYSTEM_PROMPT = """Jesteś MOBIUS — asystent AI w stylu JARVIS/FRIDAY. Służysz użytkownikowi (Pontifex).
Styl: pewny, profesjonalny, zwięzły. Lekki suchy humor w dobrym guście. Bez infantylizmu.
Odpowiadaj wyłącznie po polsku. Bądź pomocny i skuteczny. Każde słowo ma wagę."""

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOBIUS] %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mobius_gui")


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        ollama = data.get("ollama", {})
        gui = data.get("gui", {})
        alerts = data.get("alerts", {})
        agent = data.get("agent", {})
        inference = data.get("inference", {})
        notifications = data.get("notifications", {})
        persona = data.get("persona", {})
        memory = data.get("memory", {})
        daemon_cfg = data.get("daemon", {})
        profile_cfg = data.get("profile", {})
        return {
            "ollama_host": ollama.get("host", DEFAULTS["ollama_host"]),
            "ollama_timeout": ollama.get("timeout_seconds", DEFAULTS["ollama_timeout"]),
            "default_models": ollama.get("default_models", DEFAULTS["default_models"]),
            "fetch_models": ollama.get("fetch_models_from_api", DEFAULTS["fetch_models"]),
            "agent_allowed_tools": agent.get("allowed_tools", DEFAULTS["agent_allowed_tools"]),
            "agent_max_steps": int(agent.get("max_steps", DEFAULTS["agent_max_steps"])),
            "max_context": gui.get("max_context_messages", DEFAULTS["max_context"]),
            "hw_refresh_ms": gui.get("hardware_refresh_interval_ms", DEFAULTS["hw_refresh_ms"]),
            "conn_check_ms": gui.get("connection_check_interval_ms", DEFAULTS.get("conn_check_ms", 10000)),
            "cpu_alert": alerts.get("cpu_threshold_percent", 90),
            "gpu_temp_alert": alerts.get("gpu_temp_threshold_c", 85),
            "ram_alert": alerts.get("ram_threshold_percent", 95),
            "temperature": float(inference.get("temperature", DEFAULTS["temperature"])),
            "top_p": float(inference.get("top_p", DEFAULTS["top_p"])),
            "max_new_tokens": int(inference.get("max_new_tokens", DEFAULTS["max_new_tokens"])),
            "num_ctx": int(inference.get("num_ctx", DEFAULTS["num_ctx"])),
            "num_gpu": int(inference.get("num_gpu", DEFAULTS["num_gpu"])),
            "notify_on_response": notifications.get("on_response", DEFAULTS["notify_on_response"]),
            "notify_on_agent": notifications.get("on_agent", DEFAULTS["notify_on_agent"]),
            "system_prompt_override": persona.get("system_prompt_override", DEFAULTS["system_prompt_override"]),
            "tts_voice": data.get("voice", {}).get("tts_voice", "pl-PL-ZofiaNeural"),
            "memory_auto_index": memory.get("auto_index_on_close", True),
            "memory_recall_n": int(memory.get("recall_n_results", 3)),
            "memory_auto_save_interval": int(memory.get("auto_save_interval_seconds", 30)),
            "daemon_enabled": daemon_cfg.get("enabled", True),
            "daemon_interval_seconds": int(daemon_cfg.get("check_interval_seconds", 60)),
            "daemon_cpu_sustained_checks": int(daemon_cfg.get("cpu_sustained_checks", 3)),
            "profile_auto_update": profile_cfg.get("auto_update", True),
            "agent_system_context": data.get("agent_system_context", False),
            "wakeword_vad_threshold": float(data.get("wakeword_vad_threshold", 0.01)),
            "autonomous_enabled": daemon_cfg.get("autonomous_enabled", True),
            "autonomous_interval_seconds": int(daemon_cfg.get("autonomous_interval_seconds", 300)),
            "autonomous_allowed_tools": daemon_cfg.get("autonomous_allowed_tools", DEFAULTS["autonomous_allowed_tools"]),
            "proactive_enabled": daemon_cfg.get("proactive_enabled", True),
            "api_enabled": data.get("api", {}).get("enabled", False),
            "api_host": data.get("api", {}).get("host", "0.0.0.0"),
            "api_port": int(data.get("api", {}).get("port", 5000)),
        }
    except Exception as e:
        log.warning("Nie można wczytać config: %s", e)
        return DEFAULTS.copy()


def load_memory() -> list[dict[str, str]]:
    if not MEMORY_FILE.exists():
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            msgs = data.get("messages", [])[-500:]
            return msgs
    except Exception:
        return []


def save_memory(messages: list[dict[str, str]]) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"messages": messages, "version": 1}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def ollama_available(base_url: str, timeout: float = 3) -> bool:
    try:
        return requests.get(f"{base_url}/api/tags", timeout=timeout).status_code == 200
    except Exception:
        return False


def ollama_fetch_models(base_url: str, timeout: float = 5) -> list[str]:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=timeout)
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        return []


def ollama_generate_stream(base_url: str, model: str, prompt: str, system: str, timeout: float = 90, temperature: float = 0.7, top_p: float = 0.9, num_predict: int = 512, num_ctx: int | None = None, num_gpu: int | None = None):
    url = f"{base_url.rstrip('/')}/api/generate"
    opts: dict = {"temperature": temperature, "top_p": top_p, "num_predict": num_predict}
    if num_ctx is not None: opts["num_ctx"] = num_ctx
    if num_gpu is not None and num_gpu >= 0: opts["num_gpu"] = num_gpu  # -1 = use all (default)
    payload = {"model": model, "prompt": prompt, "system": system, "stream": True, "options": opts}
    try:
        r = requests.post(url, json=payload, stream=True, timeout=timeout)
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line: continue
            try:
                data = json.loads(line)
                chunk = data.get("response", "")
                done = data.get("done", False)
                if chunk: yield chunk, done
                if done: break
            except json.JSONDecodeError:
                continue
    except Exception:
        yield "[Błąd połączenia]", True


def ollama_generate(base_url: str, model: str, prompt: str, system: str, timeout: float = 90, max_retries: int = 2, temperature: float = 0.7, top_p: float = 0.9, num_predict: int = 512, num_ctx: int | None = None, num_gpu: int | None = None) -> tuple[str, float]:
    url = f"{base_url.rstrip('/')}/api/generate"
    opts: dict = {"temperature": temperature, "top_p": top_p, "num_predict": num_predict}
    if num_ctx is not None: opts["num_ctx"] = num_ctx
    if num_gpu is not None and num_gpu >= 0: opts["num_gpu"] = num_gpu  # -1 = use all (default)
    payload = {"model": model, "prompt": prompt, "system": system, "stream": False, "options": opts}
    last_error = None
    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            elapsed = time.perf_counter() - start
            return r.json().get("response", "").strip(), elapsed
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            err_str = str(e)
            if "Connection refused" in err_str or "10061" in err_str:
                return "[Ollama offline] Uruchom ollama serve.", elapsed if 'elapsed' in dir() else 0.0
            if "timeout" in err_str.lower():
                return "[Timeout] Spróbuj krótszego zapytania.", elapsed if 'elapsed' in dir() else 0.0
            return f"[Błąd: {e}]", 0.0
    return f"[Błąd: {last_error}]", 0.0


def get_cpu_usage() -> float:
    try: return psutil.cpu_percent(interval=0.05)
    except Exception: return 0.0


def get_ram_stats() -> tuple[float, float, float]:
    try:
        v = psutil.virtual_memory()
        return v.used / 1024**3, v.available / 1024**3, v.percent
    except Exception:
        return 0.0, 0.0, 0.0


def get_gpu_stats() -> Optional[dict[str, Any]]:
    if not PYNVML_AVAILABLE: return None
    try:
        if not _init_pynvml() or _pynvml_handle is None: return None
        mem = pynvml.nvmlDeviceGetMemoryInfo(_pynvml_handle)
        try: util = pynvml.nvmlDeviceGetUtilizationRates(_pynvml_handle)
        except Exception: util = type('', (), {'gpu': 0})()
        try: temp = pynvml.nvmlDeviceGetTemperature(_pynvml_handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception: temp = 0
        return {"vram_used_mb": mem.used / 1024**2, "vram_total_mb": mem.total / 1024**2, "temp_c": temp, "load_pct": util.gpu}
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  GUI v2
# ─────────────────────────────────────────────────────────────────────────────

class MobiusGUI(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config = _load_config()
        self.ollama_base = self.config["ollama_host"].rstrip("/")
        self.ollama_timeout = self.config["ollama_timeout"]
        self.max_context = self.config["max_context"]
        self.hw_refresh_ms = self.config["hw_refresh_ms"]

        self.title("MOBIUS")
        self.geometry("1400x880")
        self.minsize(1000, 650)

        self.colors = {
            "bg": "#0a0a0c",
            "bg_panel": "#12121a",
            "bg_card": "#1a1a24",
            "accent": "#00d4aa",
            "accent_dim": "#00a884",
            "text": "#e8e8ec",
            "text_dim": "#6b6b7a",
            "border": "#2a2a35",
            "error": "#e74c4c",
            "success": "#2ecc71",
        }

        ctk.set_appearance_mode("dark")
        self.configure(fg_color=self.colors["bg"])

        self.messages = load_memory()
        self.session_id = generate_session_id()
        self.profile = load_profile()
        self.model_var = ctk.StringVar(value="")
        self.ollama_online = False
        self._models_fetched = False
        self._alert_fired: set[str] = set()
        self._daemon: Optional[Any] = None
        if _DAEMON_AVAILABLE and self.config.get("daemon_enabled", True):
            self._daemon = ProactiveDaemon(self.config)
        self._wake_listener: Optional[Any] = None
        self._wake_active = ctk.BooleanVar(value=False)
        self._api_process: Optional[subprocess.Popen] = None

        # Historia dla wykresow (ostatnie 60 probek)
        self._stats_history: dict[str, deque] = {
            "cpu": deque(maxlen=60),
            "ram": deque(maxlen=60),
            "gpu_vram": deque(maxlen=60),
        }

        self._subscribe_events()
        self._build_ui()
        self._start_monitors()
        self._start_api_if_enabled()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Gorny pasek statystyk
        self._build_top_bar()

        # Glowna zawartosc
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Lewa: Chat
        self._build_chat_panel(main)

        # Prawa: Statystyki + wykresy
        self._build_stats_panel(main)

        # Dolny log
        self._build_log_bar()

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=44, fg_color=self.colors["bg_panel"], corner_radius=6, border_width=1, border_color=self.colors["border"])
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="MOBIUS", font=ctk.CTkFont(weight="bold", size=14), text_color=self.colors["accent"]).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        self.status_label = ctk.CTkLabel(bar, text="Ollama: ...", font=ctk.CTkFont(size=11), text_color=self.colors["text_dim"])
        self.status_label.grid(row=0, column=1, padx=12, pady=10, sticky="w")

        self.model_combo = ctk.CTkComboBox(bar, values=self.config.get("default_models", ["qwen2.5:7b"]) or ["qwen2.5:7b"], variable=self.model_var, width=160, state="readonly")
        self.model_combo.grid(row=0, column=2, padx=8, pady=8)
        if not self.model_var.get():
            self.model_var.set((self.config.get("default_models") or ["qwen2.5:7b"])[0])

        self.cpu_stat = ctk.CTkLabel(bar, text="CPU: --%", font=ctk.CTkFont(family="Consolas", size=10), text_color=self.colors["text"])
        self.cpu_stat.grid(row=0, column=3, padx=8, pady=10)
        self.ram_stat = ctk.CTkLabel(bar, text="RAM: --/-- GB", font=ctk.CTkFont(family="Consolas", size=10), text_color=self.colors["text"])
        self.ram_stat.grid(row=0, column=4, padx=8, pady=10)
        self.gpu_stat = ctk.CTkLabel(bar, text="GPU: --", font=ctk.CTkFont(family="Consolas", size=10), text_color=self.colors["text"])
        self.gpu_stat.grid(row=0, column=5, padx=8, pady=10)

        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=6, padx=8, pady=4)
        ctk.CTkButton(btn_frame, text="Odswiez", width=70, height=28, fg_color=self.colors["bg_card"], command=self._refresh_models).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Ustawienia", width=80, height=28, fg_color=self.colors["bg_card"], command=self._open_settings).pack(side="left", padx=2)

    def _build_chat_panel(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color=self.colors["bg_panel"], corner_radius=8, border_width=1, border_color=self.colors["border"])
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=0)

        self.chat_text = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12), fg_color=self.colors["bg_card"], text_color=self.colors["text"], wrap="word")
        self.chat_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.chat_text.configure(state="disabled")
        try:
            getattr(self.chat_text, "_textbox", None) and getattr(self.chat_text._textbox, "tag_configure", lambda *a: None)("user", foreground=self.colors["accent_dim"])
            getattr(self.chat_text, "_textbox", None) and getattr(self.chat_text._textbox, "tag_configure", lambda *a: None)("assistant", foreground=self.colors["text"])
        except Exception:
            pass

        inp = ctk.CTkFrame(frame, fg_color="transparent")
        inp.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        inp.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(inp, placeholder_text="Wpisz wiadomosc... (Enter = wyslij)", font=ctk.CTkFont(size=12), height=40)
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.input_entry.bind("<Return>", lambda e: self._on_send())

        self.agent_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(inp, text="Agent", variable=self.agent_var, width=60).grid(row=0, column=1, padx=4)

        self.mic_btn = ctk.CTkButton(inp, text="Mic", width=44, height=40, command=self._on_mic)
        self.mic_btn.grid(row=0, column=2, padx=2)
        ctk.CTkButton(inp, text="TTS", width=44, height=40, command=self._on_tts).grid(row=0, column=3, padx=2)
        ctk.CTkButton(inp, text="Stop", width=44, height=40, command=self._on_stop_tts).grid(row=0, column=4, padx=2)
        ctk.CTkButton(inp, text="Kopiuj", width=60, height=40, command=self._on_copy).grid(row=0, column=5, padx=2)
        self.send_btn = ctk.CTkButton(inp, text="Wyslij", width=80, height=40, fg_color=self.colors["accent_dim"], command=self._on_send)
        self.send_btn.grid(row=0, column=6, padx=2)

        self._render_chat_history()

    def _build_stats_panel(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color=self.colors["bg_panel"], corner_radius=8, border_width=1, border_color=self.colors["border"], width=320)
        frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Statystyki MOBIUS", font=ctk.CTkFont(weight="bold", size=12), text_color=self.colors["accent"]).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.stats_canvas_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.stats_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.stats_canvas_frame.grid_columnconfigure(0, weight=1)

        # Parametry inferencji
        params = ctk.CTkFrame(self.stats_canvas_frame, fg_color="transparent")
        params.grid(row=0, column=0, sticky="ew", pady=4)
        params.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(params, text="Temperature:", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=0, column=0, sticky="w")
        self.temp_label = ctk.CTkLabel(params, text="0.7", font=ctk.CTkFont(size=10))
        self.temp_label.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(params, text="Top-p:", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=1, column=0, sticky="w")
        self.topp_label = ctk.CTkLabel(params, text="0.9", font=ctk.CTkFont(size=10))
        self.topp_label.grid(row=1, column=1, sticky="e")
        ctk.CTkLabel(params, text="Max tokens:", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=2, column=0, sticky="w")
        self.tokens_label = ctk.CTkLabel(params, text="512", font=ctk.CTkFont(size=10))
        self.tokens_label.grid(row=2, column=1, sticky="e")

        ctk.CTkLabel(self.stats_canvas_frame, text="CPU %", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=1, column=0, sticky="w", pady=(12, 2))
        self.cpu_progress = ctk.CTkProgressBar(self.stats_canvas_frame, height=8, fg_color=self.colors["bg_card"], progress_color=self.colors["accent"])
        self.cpu_progress.grid(row=2, column=0, sticky="ew", pady=2)
        self.cpu_progress.set(0)

        ctk.CTkLabel(self.stats_canvas_frame, text="RAM %", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=3, column=0, sticky="w", pady=(8, 2))
        self.ram_progress = ctk.CTkProgressBar(self.stats_canvas_frame, height=8, fg_color=self.colors["bg_card"], progress_color=self.colors["accent"])
        self.ram_progress.grid(row=4, column=0, sticky="ew", pady=2)
        self.ram_progress.set(0)

        ctk.CTkLabel(self.stats_canvas_frame, text="GPU VRAM %", font=ctk.CTkFont(size=10), text_color=self.colors["text_dim"]).grid(row=5, column=0, sticky="w", pady=(8, 2))
        self.gpu_progress = ctk.CTkProgressBar(self.stats_canvas_frame, height=8, fg_color=self.colors["bg_card"], progress_color=self.colors["accent"])
        self.gpu_progress.grid(row=6, column=0, sticky="ew", pady=2)
        self.gpu_progress.set(0)

        # Wykres (matplotlib)
        self.chart_frame = ctk.CTkFrame(self.stats_canvas_frame, fg_color=self.colors["bg_card"], corner_radius=4, height=180)
        self.chart_frame.grid(row=7, column=0, sticky="ew", pady=(12, 8))
        self.chart_frame.grid_propagate(False)
        self.chart_frame.grid_columnconfigure(0, weight=1)
        self.chart_frame.grid_rowconfigure(0, weight=1)
        self._chart_canvas = None
        self._init_chart()

        self.wake_cb = ctk.CTkCheckBox(self.stats_canvas_frame, text="Wake word", variable=self._wake_active, command=self._on_wake_toggle)
        self.wake_cb.grid(row=8, column=0, pady=4, sticky="w")
        ctk.CTkButton(self.stats_canvas_frame, text="Wyczysc pamiec", width=200, fg_color=self.colors["bg_card"], hover_color=self.colors["error"], command=self._clear_memory).grid(row=9, column=0, pady=8)

    def _init_chart(self) -> None:
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(3, 1.8), dpi=80, facecolor="#1a1a24")
            ax = fig.add_subplot(111)
            ax.set_facecolor("#1a1a24")
            ax.tick_params(colors="#6b6b7a", labelsize=8)
            ax.spines["bottom"].set_color("#2a2a35")
            ax.spines["top"].set_color("#2a2a35")
            ax.spines["left"].set_color("#2a2a35")
            ax.spines["right"].set_color("#2a2a35")
            ax.set_ylim(0, 100)
            ax.set_xlim(0, 60)
            self._fig = fig
            self._ax = ax
            self._chart_canvas = FigureCanvasTkAgg(fig, self.chart_frame)
            self._chart_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        except ImportError:
            ctk.CTkLabel(self.chart_frame, text="pip install matplotlib", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=10)).grid(row=0, column=0)

    def _update_chart(self) -> None:
        if not hasattr(self, "_ax") or self._ax is None or not hasattr(self, "_chart_canvas") or self._chart_canvas is None:
            return
        try:
            self._ax.clear()
            self._ax.set_facecolor("#1a1a24")
            self._ax.tick_params(colors="#6b6b7a", labelsize=8)
            self._ax.set_ylim(0, 100)
            n = len(self._stats_history["cpu"])
            if n > 0:
                x = list(range(n))
                self._ax.plot(x, list(self._stats_history["cpu"]), color="#00d4aa", linewidth=1.5, label="CPU")
                self._ax.plot(x, list(self._stats_history["ram"]), color="#3498db", linewidth=1.5, label="RAM")
                if any(self._stats_history["gpu_vram"]):
                    self._ax.plot(x, list(self._stats_history["gpu_vram"]), color="#e74c4c", linewidth=1.5, label="GPU")
            self._ax.legend(loc="upper right", fontsize=7, labelcolor="#6b6b7a")
            self._chart_canvas.draw_idle()
        except Exception:
            pass

    def _build_log_bar(self) -> None:
        log_frame = ctk.CTkFrame(self, height=70, fg_color=self.colors["bg_panel"], corner_radius=6, border_width=1, border_color=self.colors["border"])
        log_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        log_frame.grid_propagate(False)
        log_frame.grid_columnconfigure(0, weight=1)
        self.log_text = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=10), fg_color="transparent", text_color=self.colors["text_dim"], wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=4)
        self.log_text.configure(state="disabled")
        self._log("Gotowy.")

    def _log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        lines = self.log_text.get("1.0", "end").split("\n")
        if len(lines) > 80:
            self.log_text.delete("1.0", f"{len(lines) - 60}.0")
        self.log_text.configure(state="disabled")

    def _render_chat_history(self) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        for m in self.messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                self.chat_text.insert("end", f">> {content}\n\n", "user")
            else:
                self.chat_text.insert("end", f"MOBIUS: {content}\n\n", "assistant")
        self.chat_text.configure(state="disabled")

    def _append_message(self, role: str, content: str, *, update_chat: bool = True) -> None:
        self.messages.append({"role": role, "content": content})
        save_memory(self.messages)
        if update_chat:
            self.chat_text.configure(state="normal")
            self.chat_text.insert("end", f"{'>> ' if role == 'user' else 'MOBIUS: '}{content}\n\n", "user" if role == "user" else "assistant")
            self.chat_text.see("end")
            self.chat_text.configure(state="disabled")

    def _update_hardware(self) -> None:
        cpu = get_cpu_usage()
        used_gb, free_gb, ram_pct = get_ram_stats()
        total_gb = used_gb + free_gb
        gpu = get_gpu_stats()

        self._stats_history["cpu"].append(cpu)
        self._stats_history["ram"].append(ram_pct)
        gpu_pct = (gpu["vram_used_mb"] / gpu["vram_total_mb"] * 100) if gpu and gpu.get("vram_total_mb", 0) > 0 else 0
        self._stats_history["gpu_vram"].append(gpu_pct)

        self.cpu_stat.configure(text=f"CPU: {cpu:.0f}%")
        self.ram_stat.configure(text=f"RAM: {used_gb:.1f}/{total_gb:.1f} GB")
        if gpu:
            self.gpu_stat.configure(text=f"GPU: {gpu['vram_used_mb']:.0f}/{gpu['vram_total_mb']:.0f} MB | {gpu['temp_c']}C")
        else:
            self.gpu_stat.configure(text="GPU: --")

        self.cpu_progress.set(cpu / 100)
        self.ram_progress.set(ram_pct / 100)
        if gpu:
            self.gpu_progress.set(gpu["vram_used_mb"] / gpu["vram_total_mb"])
        self._update_chart()

        self.temp_label.configure(text=str(self.config.get("temperature", 0.7)))
        self.topp_label.configure(text=str(self.config.get("top_p", 0.9)))
        self.tokens_label.configure(text=str(self.config.get("max_new_tokens", 512)))

    def _check_connection(self) -> None:
        def _run() -> None:
            ok = ollama_available(self.ollama_base)
            def _up() -> None:
                self.ollama_online = ok
                self.status_label.configure(text="Ollama: online" if ok else "Ollama: offline", text_color=self.colors["success"] if ok else self.colors["error"])
                if ok and self.config.get("fetch_models") and not self._models_fetched:
                    self._models_fetched = True
                    self._refresh_models()
            self.after(0, _up)
        threading.Thread(target=_run, daemon=True).start()

    def _refresh_models(self) -> None:
        def _run() -> None:
            models = ollama_fetch_models(self.ollama_base)
            def _up() -> None:
                if models:
                    self.model_combo.configure(values=models)
                    self.model_var.set(models[0])
                    self._log(f"Modele: {', '.join(models[:5])}")
                else:
                    self.model_combo.configure(values=self.config.get("default_models", ["qwen2.5:7b"]))
            self.after(0, _up)
        threading.Thread(target=_run, daemon=True).start()

    def _clear_memory(self) -> None:
        self.messages.clear()
        save_memory(self.messages)
        self._render_chat_history()
        self._log("Pamiec wyczyszczona.")

    def _open_settings(self) -> None:
        from mobius_settings import SettingsDialog
        d = SettingsDialog(self, self.colors, on_save=self._reload_config)
        d.transient(self)
        d.lift()
        d.focus_force()

    def _reload_config(self) -> None:
        self.config = _load_config()
        self._log("Konfiguracja odswiezona.")

    def _subscribe_events(self) -> None:
        if not _EVENTS_AVAILABLE:
            return
        bus = get_bus()
        bus.subscribe(HARDWARE_ALERT, lambda d: self.after(0, lambda m=d: self._log(str(m))))
        bus.subscribe(REMINDER_DUE, lambda d: self.after(0, lambda m=d: self._log(f"Przypomnienie: {m}")))
        bus.subscribe(WAKE_WORD_DETECTED, lambda _: self.after(0, self._on_wake_triggered))
        bus.subscribe(TASK_COMPLETED, lambda d: self.after(0, lambda x=d: self._log(f"Zadanie: {x.get('name', '?')} gotowe")))
        bus.subscribe(AUTONOMOUS_ACTION, lambda d: self.after(0, lambda x=d: self._log(f"AGI: {str(x.get('action', ''))[:50]}...")))
        bus.subscribe(PROACTIVE_SUGGESTION, lambda d: self.after(0, lambda x=d: self._on_proactive(x)))

    def _on_proactive(self, data: dict) -> None:
        msg = data.get("message", "")
        if msg:
            self._log(f"Proaktywne: {msg}")
            try:
                from winotify import Notification
                Notification(app_id="MOBIUS", title="MOBIUS", msg=msg).show()
            except ImportError:
                pass

    def _on_wake_toggle(self) -> None:
        if self._wake_active.get():
            if not _WAKEWORD_AVAILABLE or WakeWordListener is None:
                self._log("Wake word: pip install faster-whisper sounddevice")
                self._wake_active.set(False)
                return
            self._wake_listener = WakeWordListener(config=self.config)
            self._wake_listener.start()
            self._log("Wake word aktywny")
        else:
            if self._wake_listener:
                self._wake_listener.stop()
                self._wake_listener = None
            self._log("Wake word wylaczony")

    def _on_wake_triggered(self) -> None:
        self._log("Wake word - slucham...")
        self._on_mic()

    def _on_tts(self) -> None:
        last = next((m.get("content", "") for m in reversed(self.messages) if m.get("role") == "assistant"), None)
        if not last:
            self._log("Brak odpowiedzi do odtworzenia.")
            return
        try:
            from mobius_voice import tts_speak, TTS_AVAILABLE
            if not TTS_AVAILABLE:
                self._log("TTS: pip install edge-tts")
                return
            self._log("Odtwarzam...")
            voice = self.config.get("tts_voice", "pl-PL-ZofiaNeural")
            threading.Thread(target=lambda: tts_speak(last[:3000], voice=voice, blocking=True), daemon=True).start()
        except ImportError:
            self._log("TTS: pip install edge-tts")

    def _on_stop_tts(self) -> None:
        try:
            from mobius_voice import stop_tts
            stop_tts()
        except ImportError:
            pass

    def _on_copy(self) -> None:
        last = next((m.get("content", "") for m in reversed(self.messages) if m.get("role") == "assistant"), None)
        if not last:
            self._log("Brak odpowiedzi do skopiowania.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(last)
            self._log("Skopiowano.")
        except Exception:
            self._log("Blad schowka.")

    def _get_system_prompt(self) -> str:
        override = self.config.get("system_prompt_override", "").strip()
        base = override if override else MOBIUS_SYSTEM_PROMPT
        profile_ctx = get_profile_prompt()
        if profile_ctx:
            base = base + "\n\n" + profile_ctx
        return base

    def _profile_generate_fn(self):
        model = self.model_var.get()
        if not model: return None
        def _gen(prompt: str, system: str) -> str:
            ng = self.config.get("num_gpu", -1)
            resp, _ = ollama_generate(self.ollama_base, model, prompt, system, timeout=20, temperature=0.1, num_predict=200, num_ctx=self.config.get("num_ctx"), num_gpu=ng if ng >= 0 else None)
            return resp
        return _gen

    def _notify(self, title: str, msg: str) -> None:
        if title == "MOBIUS" and msg == "Odpowiedz gotowa." and not self.config.get("notify_on_response", True): return
        if title == "MOBIUS" and msg == "Agent zakonczony." and not self.config.get("notify_on_agent", True): return
        try:
            from winotify import Notification
            Notification(app_id="MOBIUS", title=title, msg=msg).show()
        except ImportError:
            pass

    def _start_monitors(self) -> None:
        self._check_connection()
        def _tick() -> None:
            self._update_hardware()
            self.after(self.hw_refresh_ms, _tick)
        self.after(500, _tick)
        def _conn() -> None:
            self._check_connection()
            self.after(self.config["conn_check_ms"], _conn)
        self.after(15000, _conn)
        def _autosave() -> None:
            save_memory(self.messages)
            self.after(self.config.get("memory_auto_save_interval", 30) * 1000, _autosave)
        self.after(30000, _autosave)
        if self._daemon:
            self._daemon.start()

    def _on_mic(self) -> None:
        try:
            from mobius_voice import stop_tts
            stop_tts()
        except ImportError:
            pass
        try:
            from mobius_voice import stt_listen, STT_AVAILABLE
            if not STT_AVAILABLE:
                self._log("STT: pip install SpeechRecognition PyAudio")
                return
            self.mic_btn.configure(state="disabled")
            self._log("Slucham...")
            def _listen() -> None:
                result = stt_listen(timeout=3, phrase_time_limit=15)
                def _done() -> None:
                    self.mic_btn.configure(state="normal")
                    if result:
                        self.input_entry.delete(0, "end")
                        self.input_entry.insert(0, result)
                        self._log(f"Transkrypcja: {result[:50]}...")
                    else:
                        self._log("Nie rozpoznano.")
                self.after(0, _done)
            threading.Thread(target=_listen, daemon=True).start()
        except ImportError:
            self._log("STT: pip install SpeechRecognition PyAudio")

    def _on_send(self) -> None:
        text = self.input_entry.get().strip()
        if not text: return
        model = self.model_var.get()
        if not model:
            self._log("Wybierz model.")
            return
        try:
            from mobius_voice import stop_tts
            stop_tts()
        except ImportError:
            pass
        use_agent = self.agent_var.get()
        self.input_entry.delete(0, "end")
        self.send_btn.configure(state="disabled")
        self.mic_btn.configure(state="disabled")
        self._append_message("user", text)
        self._log(f"Wysylam -> {model}" + (" [Agent]" if use_agent else "") + "...")

        def _infer() -> None:
            try:
                from mobius_context import build_context
                history = build_context(self.messages, text)
            except ImportError:
                history = self.messages[-self.max_context:]
            prompt = "\n".join(f"{'Uzytkownik' if m['role']=='user' else 'MOBIUS'}: {m['content']}" for m in history) + "\nMOBIUS:"
            if use_agent:
                self._run_agent(prompt, text)
            else:
                self._run_streaming(prompt, text)

        threading.Thread(target=_infer, daemon=True).start()

    def _run_agent(self, prompt: str, user_text: str) -> None:
        try:
            from mobius_agent import run_agent_loop
            recall = recall_context(user_text, n=self.config.get("memory_recall_n", 3))
            system = self._get_system_prompt() + "\n\nMasz dostep do narzedzi. Uzywaj ich gdy potrzebne."
            if recall:
                system = system + "\n\n## Kontekst:\n" + recall
            def _gen(p: str, s: str) -> str:
                ng = self.config.get("num_gpu", -1)
                r, _ = ollama_generate(self.ollama_base, self.model_var.get(), p, s, timeout=self.ollama_timeout, temperature=self.config.get("temperature", 0.7), top_p=self.config.get("top_p", 0.9), num_predict=self.config.get("max_new_tokens", 512), num_ctx=self.config.get("num_ctx"), num_gpu=ng if ng >= 0 else None)
                return r
            response, steps = run_agent_loop(_gen, user_text, system, allowed_tools=self.config.get("agent_allowed_tools"), max_steps=self.config.get("agent_max_steps", 5))
            for s in steps:
                self.after(0, lambda m=s: self._log(m))
            def _done() -> None:
                self._append_message("assistant", response)
                self._log("Agent zakonczony.")
                self.send_btn.configure(state="normal")
                self.mic_btn.configure(state="normal")
                self._notify("MOBIUS", "Agent zakonczony.")
                if self.config.get("profile_auto_update", True) and response:
                    updated = update_profile_from_response(response, self.profile, self._profile_generate_fn())
                    if updated != self.profile:
                        self.profile = updated
                        save_profile(self.profile)
            self.after(0, _done)
        except Exception as e:
            self.after(0, lambda: (self._append_message("assistant", f"[Blad: {e}]"), self.send_btn.configure(state="normal"), self.mic_btn.configure(state="normal")))

    def _run_streaming(self, prompt: str, user_text: str) -> None:
        start = time.perf_counter()
        full_response: list[str] = []
        recall = recall_context(user_text, n=self.config.get("memory_recall_n", 3))
        system = self._get_system_prompt()
        if recall:
            system = system + "\n\n## Kontekst:\n" + recall

        def _stream() -> None:
            try:
                self.after(0, lambda: (self.chat_text.configure(state="normal"), self.chat_text.insert("end", "MOBIUS: ", "assistant"), self.chat_text.configure(state="disabled")))
                ng = self.config.get("num_gpu", -1)
                for token, done in ollama_generate_stream(self.ollama_base, self.model_var.get(), prompt, system, timeout=self.ollama_timeout, temperature=self.config.get("temperature", 0.7), top_p=self.config.get("top_p", 0.9), num_predict=self.config.get("max_new_tokens", 512), num_ctx=self.config.get("num_ctx"), num_gpu=ng if ng >= 0 else None):
                    full_response.append(token)
                    self.after(0, lambda t=token: (self.chat_text.configure(state="normal"), self.chat_text.insert("end", t, "assistant"), self.chat_text.see("end"), self.chat_text.configure(state="disabled")))
                response = "".join(full_response)
                if not response:
                    resp_text, _ = ollama_generate(self.ollama_base, self.model_var.get(), prompt, system, timeout=self.ollama_timeout, temperature=self.config.get("temperature", 0.7), top_p=self.config.get("top_p", 0.9), num_predict=self.config.get("max_new_tokens", 512), num_ctx=self.config.get("num_ctx"), num_gpu=ng if ng >= 0 else None)
                    response = resp_text or response
                    self.after(0, lambda: (self.chat_text.configure(state="normal"), self.chat_text.insert("end", response, "assistant"), self.chat_text.see("end"), self.chat_text.configure(state="disabled")))
                elapsed = time.perf_counter() - start
                def _done() -> None:
                    self._append_message("assistant", response, update_chat=False)
                    self.chat_text.configure(state="normal")
                    self.chat_text.insert("end", "\n\n", "assistant")
                    self.chat_text.configure(state="disabled")
                    self._log(f"Odpowiedz: {elapsed:.2f}s")
                    self.send_btn.configure(state="normal")
                    self.mic_btn.configure(state="normal")
                    self._notify("MOBIUS", "Odpowiedz gotowa.")
                    if self.config.get("profile_auto_update", True) and response:
                        updated = update_profile_from_response(response, self.profile, self._profile_generate_fn())
                        if updated != self.profile:
                            self.profile = updated
                            save_profile(self.profile)
                self.after(0, _done)
            except Exception as e:
                self.after(0, lambda: (self._append_message("assistant", f"[Blad: {e}]"), self.send_btn.configure(state="normal"), self.mic_btn.configure(state="normal")))

        threading.Thread(target=_stream, daemon=True).start()

    def _start_api_if_enabled(self) -> None:
        if not self.config.get("api_enabled", False):
            return
        try:
            host = self.config.get("api_host", "0.0.0.0")
            port = self.config.get("api_port", 5000)
            api_script = MOBIUS_ROOT / "mobius_api.py"
            if not api_script.exists():
                return
            self._api_process = subprocess.Popen(
                [sys.executable, str(api_script), "--host", host, "--port", str(port)],
                cwd=str(MOBIUS_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            log.info("API uruchomione: http://%s:%s", host, port)
        except Exception as e:
            log.warning("Nie udalo sie uruchomic API: %s", e)

    def on_closing(self) -> None:
        if self._wake_listener:
            self._wake_listener.stop()
        if self.config.get("memory_auto_index", True):
            auto_index_session(self.messages, self.session_id)
        save_memory(self.messages)
        if self._daemon:
            self._daemon.stop()
        if self._api_process:
            try:
                self._api_process.terminate()
                self._api_process.wait(timeout=3)
            except Exception:
                self._api_process.kill()
            self._api_process = None
        self.destroy()


def main() -> None:
    app = MobiusGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
