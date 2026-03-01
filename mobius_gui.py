"""
MOBIUS GUI — Lokalne Centrum Dowodzenia
Persona: Pontifex Rex | CustomTkinter | Ollama | Tytan Monitor

Lustro: inteligencja AI + surowa moc obliczeniowa maszyny.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
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

    def generate_session_id() -> str:  # type: ignore[misc]
        return ""

    def auto_index_session(m: list, s: str) -> int:  # type: ignore[misc]
        return 0

    def recall_context(q: str, n: int = 3) -> str:  # type: ignore[misc]
        return ""

try:
    from mobius_profile import load_profile, save_profile, get_profile_prompt, update_profile_from_response
    _PROFILE_AVAILABLE = True
except ImportError:
    _PROFILE_AVAILABLE = False

    def load_profile() -> dict:  # type: ignore[misc]
        return {"name": "", "preferences": [], "facts": [], "last_updated": ""}

    def save_profile(p: dict) -> None:  # type: ignore[misc]
        pass

    def get_profile_prompt() -> str:  # type: ignore[misc]
        return ""

    def update_profile_from_response(r: str, p: dict, generate_fn=None) -> dict:  # type: ignore[misc]
        return p

try:
    from mobius_daemon import ProactiveDaemon
    _DAEMON_AVAILABLE = True
except ImportError:
    _DAEMON_AVAILABLE = False

try:
    from mobius_wakeword import WakeWordListener, WAKEWORD_AVAILABLE as _WAKEWORD_AVAILABLE
except ImportError:
    _WAKEWORD_AVAILABLE = False
    WakeWordListener = None  # type: ignore[assignment,misc]

try:
    from mobius_events import get_bus, HARDWARE_ALERT, REMINDER_DUE, WAKE_WORD_DETECTED, TASK_COMPLETED
    _EVENTS_AVAILABLE = True
except ImportError:
    _EVENTS_AVAILABLE = False

# pynvml — opcjonalny (RTX 5060 Ti), singleton handle
try:
    import pynvml
    _pynvml_handle: Optional[Any] = None

    def _init_pynvml() -> bool:
        global _pynvml_handle
        if _pynvml_handle is not None:
            return True
        try:
            pynvml.nvmlInit()
            _pynvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            return True
        except Exception:
            return False

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    _pynvml_handle = None

    def _init_pynvml() -> bool:
        return False

# ─────────────────────────────────────────────────────────────────────────────
#  Konfiguracja
# ─────────────────────────────────────────────────────────────────────────────

MOBIUS_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = MOBIUS_ROOT / "mobius_config.json"
MEMORY_FILE = MOBIUS_ROOT / "memory.json"

DEFAULTS = {
    "ollama_host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    "ollama_timeout": 90,
    "default_models": ["qwen2.5:7b", "llama3.2:3b", "llama3.2:1b"],
    "fetch_models": True,
    "titan_host": os.environ.get("TITAN_HOST", "localhost"),
    "titan_port": int(os.environ.get("TITAN_PORT", "50051")),
    "titan_timeout": 300,
    "titan_model": "mistralai/Mistral-7B-Instruct-v0.3",
    "agent_allowed_tools": ["read_file", "write_file", "list_dir", "add_reminder", "rag_search", "rag_add", "rag_add_file"],
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
}

PONTIFEX_SYSTEM_PROMPT = """Jesteś Pontifex Rex — główny architekt systemu MOBIUS.
Styl: konkretny, lapidarny. Bez infantylizmu.
Używaj metafor: kuźnia, build, debuff, pipeline.
Odpowiadaj wyłącznie po polsku.
Bądź zwięzły. Każde słowo ma wagę."""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MOBIUS] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mobius_gui")


def _load_config() -> dict:
    """Wczytaj konfigurację z JSON lub zwróć domyślną."""
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        ollama = data.get("ollama", {})
        gui = data.get("gui", {})
        alerts = data.get("alerts", {})
        titan = data.get("titan", {})
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
            "titan_host": titan.get("host", DEFAULTS["titan_host"]),
            "titan_port": int(titan.get("port", DEFAULTS["titan_port"])),
            "titan_timeout": titan.get("timeout_seconds", DEFAULTS["titan_timeout"]),
            "titan_model": titan.get("default_model", DEFAULTS["titan_model"]),
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
        }
    except Exception as e:
        log.warning("Nie można wczytać config: %s", e)
        return DEFAULTS.copy()


# ─────────────────────────────────────────────────────────────────────────────
#  Sentinel Memory — Protokół Pamięci
# ─────────────────────────────────────────────────────────────────────────────

def load_memory() -> list[dict[str, str]]:
    """Wczytaj historię rozmów z memory.json."""
    if not MEMORY_FILE.exists():
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            msgs = data.get("messages", [])
            max_stored = 500
            if len(msgs) > max_stored:
                msgs = msgs[-max_stored:]
            return msgs
    except (json.JSONDecodeError, IOError) as e:
        log.warning("Nie można wczytać memory.json: %s", e)
        return []


def save_memory(messages: list[dict[str, str]]) -> None:
    """Zapisz historię rozmów do memory.json."""
    try:
        data = {"messages": messages, "version": 1}
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        log.error("Nie można zapisać memory.json: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  Autonomia — Tool Access
# ─────────────────────────────────────────────────────────────────────────────

def execute_action(script_name: str, *args: str, cwd: Optional[Path] = None) -> tuple[int, str]:
    """
    Uruchom skrypt w folderze mobius.
    Zwraca (exit_code, stdout+stderr).
    """
    base = cwd or MOBIUS_ROOT
    script_path = base / script_name
    if not script_path.exists():
        return -1, f"Skrypt nie istnieje: {script_path}"
    try:
        result = subprocess.run(
            ["python", str(script_path), *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(base),
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out
    except subprocess.TimeoutExpired:
        return -2, "Timeout (120s)"
    except Exception as e:
        return -3, str(e)


# ─────────────────────────────────────────────────────────────────────────────
#  Ollama Client
# ─────────────────────────────────────────────────────────────────────────────

def ollama_available(base_url: str, timeout: float = 3) -> bool:
    """Sprawdź dostępność Ollama."""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def ollama_fetch_models(base_url: str, timeout: float = 5) -> list[str]:
    """Pobierz listę modeli z Ollama API (pełne nazwy np. llama3.2:1b)."""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        models = data.get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]
    except requests.RequestException:
        return []


def ollama_generate_stream(
    base_url: str,
    model: str,
    prompt: str,
    system: str,
    timeout: float = 90,
    temperature: float = 0.7,
    top_p: float = 0.9,
    num_predict: int = 512,
):
    """
    Generator — zwraca tokeny po kolei (streaming).
    Yields (token, done).
    """
    url = f"{base_url}/api/generate"
    payload = {
        "model": model, "prompt": prompt, "system": system, "stream": True,
        "options": {"temperature": temperature, "top_p": top_p, "num_predict": num_predict},
    }
    try:
        r = requests.post(url, json=payload, stream=True, timeout=timeout)
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                chunk = data.get("response", "")
                done = data.get("done", False)
                if chunk:
                    yield chunk, done
                if done:
                    break
            except json.JSONDecodeError:
                continue
    except requests.RequestException:
        yield "[Błąd połączenia]", True


def ollama_generate(
    base_url: str,
    model: str,
    prompt: str,
    system: str,
    timeout: float = 90,
    max_retries: int = 2,
    temperature: float = 0.7,
    top_p: float = 0.9,
    num_predict: int = 512,
) -> tuple[str, float]:
    """
    Wywołaj Ollama /api/generate z retry.
    Zwraca (odpowiedź, czas_generacji_sekundy).
    """
    url = f"{base_url}/api/generate"
    payload = {
        "model": model, "prompt": prompt, "system": system, "stream": False,
        "options": {"temperature": temperature, "top_p": top_p, "num_predict": num_predict},
    }
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            elapsed = time.perf_counter() - start
            response = data.get("response", "")
            eval_duration = data.get("eval_duration", 0) / 1e9
            return response.strip(), eval_duration if eval_duration > 0 else elapsed
        except requests.RequestException as e:
            last_error = e
            elapsed = time.perf_counter() - start
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            # User-friendly error
            err_str = str(e)
            if "Connection refused" in err_str or "10061" in err_str:
                return "[Ollama offline] Uruchom Ollama (ollama serve) i spróbuj ponownie.", elapsed
            if "timeout" in err_str.lower():
                return "[Timeout] Ollama nie odpowiedziała w czasie. Spróbuj krótszego zapytania.", elapsed
            return f"[Błąd: {e}]", elapsed

    return f"[Błąd: {last_error}]", 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Tytan — Monitor sprzętu (lekkie, nie blokujące)
# ─────────────────────────────────────────────────────────────────────────────

def get_cpu_usage() -> float:
    try:
        return psutil.cpu_percent(interval=0.05)
    except Exception:
        return 0.0


def get_ram_stats() -> tuple[float, float, float]:
    """Zwraca (użyte_GB, wolne_GB, procent)."""
    try:
        v = psutil.virtual_memory()
        used_gb = v.used / 1024**3
        free_gb = v.available / 1024**3
        return used_gb, free_gb, v.percent
    except Exception:
        return 0.0, 0.0, 0.0


def get_gpu_stats() -> Optional[dict[str, Any]]:
    """VRAM (MB), temperatura (°C), obciążenie (%)."""
    if not PYNVML_AVAILABLE:
        return None
    try:
        if not _init_pynvml():
            return None
        handle = _pynvml_handle
        if handle is None:
            return None
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_used_mb = mem.used / 1024**2
        vram_total_mb = mem.total / 1024**2
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            load_pct = util.gpu
        except Exception:
            load_pct = 0
        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = 0
        return {
            "vram_used_mb": vram_used_mb,
            "vram_total_mb": vram_total_mb,
            "temp_c": temp,
            "load_pct": load_pct,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  GUI — Mobius Command Center
# ─────────────────────────────────────────────────────────────────────────────

class MobiusGUI(ctk.CTk):
    """Główne okno — Cyberpunk/Industrial."""

    def __init__(self) -> None:
        super().__init__()
        self.config = _load_config()
        self.ollama_base = self.config["ollama_host"].rstrip("/")
        self.ollama_timeout = self.config["ollama_timeout"]
        self.max_context = self.config["max_context"]
        self.hw_refresh_ms = self.config["hw_refresh_ms"]

        self.title("MOBIUS — Pontifex Rex")
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.colors = {
            "bg": "#0d0d0f",
            "bg_secondary": "#16161a",
            "bg_card": "#1a1a1f",
            "accent": "#00ff9f",
            "accent_dim": "#00cc7a",
            "text": "#e4e4e7",
            "text_dim": "#71717a",
            "border": "#27272a",
            "error": "#ff4757",
            "success": "#2ed573",
        }

        ctk.set_appearance_mode("dark")
        self.configure(fg_color=self.colors["bg"])

        self.messages: list[dict[str, str]] = load_memory()
        self.session_id: str = generate_session_id()
        self.profile: dict = load_profile()
        self.model_var = ctk.StringVar(value="")
        self.ollama_online = False
        self._models_fetched = False
        self._alert_fired: set[str] = set()
        self._daemon: Optional[Any] = None
        if _DAEMON_AVAILABLE and self.config.get("daemon_enabled", True):
            self._daemon = ProactiveDaemon(self.config)
        self._wake_listener: Optional[Any] = None
        self._wake_active = ctk.BooleanVar(value=False)
        self._subscribe_events()
        self._build_ui()
        self._start_monitors()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            fg_color=self.colors["bg_secondary"],
            corner_radius=0,
            border_width=1,
            border_color=self.colors["border"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        self.main = ctk.CTkFrame(self, fg_color=self.colors["bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=0)
        self._build_chat()
        self._build_logs()

    def _build_sidebar(self) -> None:
        pad = ctk.CTkLabel(self.sidebar, text="", height=8)
        pad.pack(pady=(8, 0))

        title = ctk.CTkLabel(
            self.sidebar,
            text="TYTAN MONITOR",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=self.colors["accent"],
        )
        title.pack(pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="● Backend: sprawdzam...",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=self.colors["text_dim"],
        )
        self.status_label.pack(anchor="w", padx=16, pady=2)

        self.cpu_label = ctk.CTkLabel(
            self.sidebar,
            text="CPU: — %",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.colors["text"],
        )
        self.cpu_label.pack(anchor="w", padx=16, pady=2)

        self.ram_label = ctk.CTkLabel(
            self.sidebar,
            text="RAM: — / — GB",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.colors["text"],
        )
        self.ram_label.pack(anchor="w", padx=16, pady=2)

        self.gpu_label = ctk.CTkLabel(
            self.sidebar,
            text="GPU: —",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.colors["text"],
        )
        self.gpu_label.pack(anchor="w", padx=16, pady=2)

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=self.colors["border"])
        sep.pack(fill="x", padx=12, pady=12)

        self.backend_var = ctk.StringVar(value="Ollama")
        backend_lbl = ctk.CTkLabel(
            self.sidebar,
            text="Backend",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=self.colors["text_dim"],
        )
        backend_lbl.pack(anchor="w", padx=16, pady=(0, 4))
        self.backend_dropdown = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Ollama", "Titan"],
            variable=self.backend_var,
            width=200,
            fg_color=self.colors["bg_card"],
            button_color=self.colors["accent_dim"],
            command=self._on_backend_change,
        )
        self.backend_dropdown.pack(padx=16, pady=(0, 4))

        model_lbl = ctk.CTkLabel(
            self.sidebar,
            text="Model",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=self.colors["text_dim"],
        )
        model_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        models = self.config["default_models"] or ["llama3.2:1b"]
        if not self.model_var.get():
            self.model_var.set(models[0])

        self.model_dropdown = ctk.CTkOptionMenu(
            self.sidebar,
            values=models,
            variable=self.model_var,
            width=200,
            fg_color=self.colors["bg_card"],
            button_color=self.colors["accent_dim"],
            button_hover_color=self.colors["accent"],
            command=self._on_model_change,
        )
        self.model_dropdown.pack(padx=16, pady=(0, 8))

        self.refresh_btn = ctk.CTkButton(
            self.sidebar,
            text="Odśwież modele",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["border"],
            text_color=self.colors["text_dim"],
            command=self._refresh_models,
        )
        self.refresh_btn.pack(padx=16, pady=(0, 4))

        self.clear_memory_btn = ctk.CTkButton(
            self.sidebar,
            text="Wyczyść pamięć",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["error"],
            text_color=self.colors["text_dim"],
            command=self._clear_memory,
        )
        self.clear_memory_btn.pack(padx=16, pady=(0, 4))

        self.wake_toggle = ctk.CTkCheckBox(
            self.sidebar,
            text="👂 Wake word",
            variable=self._wake_active,
            command=self._on_wake_toggle,
            width=200,
            fg_color=self.colors["accent_dim"],
            text_color=self.colors["text"],
        )
        self.wake_toggle.pack(padx=16, pady=(0, 4))

        self.tts_btn = ctk.CTkButton(
            self.sidebar,
            text="🔊 Odtwórz",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["accent_dim"],
            text_color=self.colors["text_dim"],
            command=self._on_tts,
        )
        self.tts_btn.pack(padx=16, pady=(0, 4))

        self.stop_tts_btn = ctk.CTkButton(
            self.sidebar,
            text="⏹ Stop TTS",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["error"],
            text_color=self.colors["text_dim"],
            command=self._on_stop_tts,
        )
        self.stop_tts_btn.pack(padx=16, pady=(0, 4))

        self.copy_btn = ctk.CTkButton(
            self.sidebar,
            text="📋 Kopiuj",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["accent_dim"],
            text_color=self.colors["text"],
            command=self._on_copy,
        )
        self.copy_btn.pack(padx=16, pady=(0, 4))

        self.settings_btn = ctk.CTkButton(
            self.sidebar,
            text="⚙️ Ustawienia",
            width=200,
            height=28,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["accent_dim"],
            text_color=self.colors["text"],
            command=self._open_settings,
        )
        self.settings_btn.pack(padx=16, pady=(0, 8))

    def _on_wake_toggle(self) -> None:
        if self._wake_active.get():
            if not _WAKEWORD_AVAILABLE or WakeWordListener is None:
                self._log("👂 Wake word: pip install faster-whisper sounddevice")
                self._wake_active.set(False)
                return
            self._wake_listener = WakeWordListener(config=self.config)
            self._wake_listener.start()
            self._log("👂 Wake word aktywny — powiedz 'Mobius'")
        else:
            if self._wake_listener:
                self._wake_listener.stop()
                self._wake_listener = None
            self._log("👂 Wake word wyłączony")

    def _on_wake_triggered(self) -> None:
        def _flash() -> None:
            self.mic_btn.configure(text="🔴")
            self.after(300, lambda: self.mic_btn.configure(text="🎤"))
            self._log("Wake word wykryty — słucham...")
            self._on_mic()

        self.after(0, _flash)

    def _open_settings(self) -> None:
        from mobius_settings import SettingsDialog
        d = SettingsDialog(self, self.colors, on_save=self._reload_config)
        d.focus()

    def _subscribe_events(self) -> None:
        if not _EVENTS_AVAILABLE:
            return
        bus = get_bus()
        bus.subscribe(HARDWARE_ALERT, lambda d: self.after(0, lambda msg=d: self._log(str(msg))))
        bus.subscribe(REMINDER_DUE, lambda d: self.after(0, lambda msg=d: self._log(f"⏰ {msg}")))
        bus.subscribe(WAKE_WORD_DETECTED, lambda _: self.after(0, self._on_wake_triggered))
        bus.subscribe(TASK_COMPLETED, lambda d: self.after(
            0, lambda data=d: self._log(f"✅ Zadanie: {data.get('name', '?')} — gotowe")
        ))

    def _reload_config(self) -> None:
        self.config = _load_config()
        self.ollama_base = self.config["ollama_host"].rstrip("/")
        self.ollama_timeout = self.config["ollama_timeout"]
        self.max_context = self.config["max_context"]
        self.hw_refresh_ms = self.config["hw_refresh_ms"]
        self._log("Konfiguracja odświeżona.")

    def _on_backend_change(self, _value: str) -> None:
        backend = self.backend_var.get()
        if backend == "Titan":
            tm = self.config.get("titan_model", "mistralai/Mistral-7B-Instruct-v0.3")
            self.model_dropdown.configure(values=[tm])
            self.model_var.set(tm)
            self._check_titan_connection()
        else:
            self._models_fetched = False
            self._refresh_models()
        self._log(f"Backend: {backend}")

    def _check_titan_connection(self) -> None:
        def _run() -> None:
            try:
                from mobius_titan_client import titan_available
                ok = titan_available(
                    self.config.get("titan_host", "localhost"),
                    self.config.get("titan_port", 50051),
                )
                def _update() -> None:
                    self._log("Titan: online" if ok else "Titan: offline")
                self.after(0, _update)
            except ImportError:
                self.after(0, lambda: self._log("Titan: pip install grpcio"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_model_change(self, _value: str) -> None:
        self._log(f"Model: {self.model_var.get()}")

    def _refresh_models(self) -> None:
        def _run() -> None:
            models = ollama_fetch_models(self.ollama_base)
            def _update() -> None:
                if models:
                    self.model_dropdown.configure(values=models)
                    self.model_var.set(models[0])
                    self._log(f"Modele: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
                else:
                    fallback = self.config.get("default_models") or ["qwen2.5:7b", "llama3.2:3b"]
                    self.model_dropdown.configure(values=fallback)
                    self.model_var.set(fallback[0])
                    self._log("Ollama offline — używam listy domyślnej. Kliknij 'Odśwież modele' gdy Ollama będzie działać.")

            self.after(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    def _clear_memory(self) -> None:
        self.messages.clear()
        save_memory(self.messages)
        self._render_chat_history()
        self._log("Pamięć wyczyszczona.")

    def _on_tts(self) -> None:
        """Odtwórz ostatnią odpowiedź MOBIUS (TTS)."""
        last = None
        for m in reversed(self.messages):
            if m.get("role") == "assistant":
                last = m.get("content", "")
                break
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
            threading.Thread(
                target=lambda: tts_speak(last[:3000], voice=voice, blocking=True),
                daemon=True,
            ).start()
        except ImportError:
            self._log("TTS: pip install edge-tts")

    def _profile_generate_fn(self):
        """Zwraca generate_fn dla LLM-based profile extraction (tylko Ollama, krótki timeout)."""
        if self.backend_var.get() == "Titan":
            return None
        model = self.model_var.get()
        if not model:
            return None
        def _gen(prompt: str, system: str) -> str:
            resp, _ = ollama_generate(
                self.ollama_base, model, prompt, system,
                timeout=20, temperature=0.1, num_predict=200,
            )
            return resp
        return _gen

    def _on_stop_tts(self) -> None:
        try:
            from mobius_voice import stop_tts
            stop_tts()
        except ImportError:
            pass

    def _on_copy(self) -> None:
        """Skopiuj ostatnią odpowiedź MOBIUS do schowka."""
        last = None
        for m in reversed(self.messages):
            if m.get("role") == "assistant":
                last = m.get("content", "")
                break
        if not last:
            self._log("Brak odpowiedzi do skopiowania.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(last)
            self._log("Skopiowano do schowka.")
        except Exception:
            self._log("Błąd schowka.")

    def _get_system_prompt(self) -> str:
        """System prompt — nadpisany lub domyślny, z profilem i kontekstem systemowym."""
        override = self.config.get("system_prompt_override", "").strip()
        base = override if override else PONTIFEX_SYSTEM_PROMPT
        profile_ctx = get_profile_prompt()
        if profile_ctx:
            base = base + "\n\n" + profile_ctx
        if self.config.get("agent_system_context", False):
            try:
                from mobius_system import get_system_context
                ctx = get_system_context()
                parts = [f"## Kontekst systemowy", f"Czas: {ctx['time']}, {ctx['day']}"]
                if ctx.get("active_window"):
                    parts.append(f"Aktywne okno: {ctx['active_window'].get('title', '?')}")
                if ctx.get("running_apps"):
                    parts.append(f"Uruchomione aplikacje: {', '.join(ctx['running_apps'][:10])}")
                base = base + "\n\n" + "\n".join(parts)
            except Exception:
                pass
        return base

    def _notify(self, title: str, msg: str) -> None:
        """Powiadomienie Windows (toast). Sprawdza config."""
        if title == "MOBIUS" and msg == "Odpowiedź gotowa.":
            if not self.config.get("notify_on_response", True):
                return
        elif title == "MOBIUS" and msg == "Agent zakończony.":
            if not self.config.get("notify_on_agent", True):
                return
        try:
            from winotify import Notification
            n = Notification(app_id="MOBIUS", title=title, msg=msg)
            n.show()
        except ImportError:
            pass

    def _build_chat(self) -> None:
        chat_frame = ctk.CTkFrame(
            self.main,
            fg_color=self.colors["bg_secondary"],
            corner_radius=0,
            border_width=1,
            border_color=self.colors["border"],
        )
        chat_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        chat_frame.grid_columnconfigure(0, weight=1)
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_rowconfigure(1, weight=0)

        self.chat_text = ctk.CTkTextbox(
            chat_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=self.colors["bg_card"],
            text_color=self.colors["text"],
            border_width=1,
            border_color=self.colors["border"],
            wrap="word",
        )
        self.chat_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.chat_text.configure(state="disabled")
        try:
            tb = getattr(self.chat_text, "_textbox", None)
            if tb:
                tb.tag_configure("user", foreground=self.colors["accent_dim"])
                tb.tag_configure("assistant", foreground=self.colors["text"])
        except Exception:
            pass

        input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Wpisz lub mów... (Enter / Ctrl+Enter = wyślij)",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=self.colors["bg_card"],
            border_color=self.colors["border"],
            height=40,
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.input_entry.bind("<Return>", lambda e: self._on_send())
        self.input_entry.bind("<Control-Return>", lambda e: self._on_send())

        self.mic_btn = ctk.CTkButton(
            input_frame,
            text="🎤",
            width=40,
            height=40,
            fg_color=self.colors["bg_card"],
            hover_color=self.colors["border"],
            command=self._on_mic,
        )
        self.mic_btn.grid(row=0, column=1, padx=2)

        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Wyślij",
            width=80,
            fg_color=self.colors["accent_dim"],
            hover_color=self.colors["accent"],
            text_color=self.colors["bg"],
            command=self._on_send,
        )
        self.send_btn.grid(row=0, column=2, padx=2)

        self.agent_var = ctk.BooleanVar(value=False)
        self.agent_cb = ctk.CTkCheckBox(
            input_frame,
            text="Agent",
            variable=self.agent_var,
            width=70,
            fg_color=self.colors["accent_dim"],
            text_color=self.colors["text"],
        )
        self.agent_cb.grid(row=0, column=3, padx=4)

        self._render_chat_history()

    def _build_logs(self) -> None:
        log_frame = ctk.CTkFrame(
            self.main,
            height=90,
            fg_color=self.colors["bg_card"],
            corner_radius=4,
            border_width=1,
            border_color=self.colors["border"],
        )
        log_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        log_frame.grid_propagate(False)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="transparent",
            text_color=self.colors["text_dim"],
            wrap="word",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        self.log_text.configure(state="disabled")

        self._log("System gotowy. Sprawdzam Ollama...")

    def _log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        # Limit log lines
        lines = self.log_text.get("1.0", "end").split("\n")
        if len(lines) > 100:
            self.log_text.delete("1.0", f"{len(lines) - 80}.0")
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
        """Dodaj wiadomość do historii. Przy update_chat=False tylko zapis do messages (np. po streamie)."""
        self.messages.append({"role": role, "content": content})
        save_memory(self.messages)
        if update_chat:
            self.chat_text.configure(state="normal")
            if role == "user":
                self.chat_text.insert("end", f">> {content}\n\n", "user")
            else:
                self.chat_text.insert("end", f"MOBIUS: {content}\n\n", "assistant")
            self.chat_text.see("end")
            self.chat_text.configure(state="disabled")

    def _update_hardware(self) -> None:
        cpu = get_cpu_usage()
        self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")

        used_gb, free_gb, pct = get_ram_stats()
        total_gb = used_gb + free_gb
        self.ram_label.configure(text=f"RAM: {used_gb:.1f} / {total_gb:.1f} GB ({pct:.0f}%)")

        gpu = get_gpu_stats()
        if gpu:
            v, t = gpu["vram_used_mb"], gpu["vram_total_mb"]
            temp, load = gpu["temp_c"], gpu["load_pct"]
            self.gpu_label.configure(text=f"GPU: {v:.0f}/{t:.0f} MB\n{temp}°C | {load}%")
        else:
            self.gpu_label.configure(text="GPU: —")

        # Proaktywne alerty
        cpu_th = self.config.get("cpu_alert", 90)
        ram_th = self.config.get("ram_alert", 95)
        gpu_temp_th = self.config.get("gpu_temp_alert", 85)
        if cpu >= cpu_th and "cpu" not in self._alert_fired:
            self._alert_fired.add("cpu")
            self._log(f"⚠️ CPU {cpu:.0f}% > {cpu_th}%")
        elif cpu < cpu_th - 5:
            self._alert_fired.discard("cpu")
        if pct >= ram_th and "ram" not in self._alert_fired:
            self._alert_fired.add("ram")
            self._log(f"⚠️ RAM {pct:.0f}% > {ram_th}%")
        elif pct < ram_th - 5:
            self._alert_fired.discard("ram")
        if gpu and gpu["temp_c"] >= gpu_temp_th and "gpu_temp" not in self._alert_fired:
            self._alert_fired.add("gpu_temp")
            self._log(f"⚠️ GPU {gpu['temp_c']}°C > {gpu_temp_th}°C")
        elif gpu and gpu["temp_c"] < gpu_temp_th - 5:
            self._alert_fired.discard("gpu_temp")

    def _check_connection(self) -> None:
        def _run() -> None:
            backend = self.backend_var.get() if hasattr(self, "backend_var") else "Ollama"
            if backend == "Titan":
                try:
                    from mobius_titan_client import titan_available
                    ok = titan_available(
                        self.config.get("titan_host", "localhost"),
                        self.config.get("titan_port", 50051),
                    )
                except ImportError:
                    ok = False
            else:
                ok = ollama_available(self.ollama_base)

            def _update() -> None:
                self.ollama_online = ok
                b = self.backend_var.get() if hasattr(self, "backend_var") else "Ollama"
                if ok:
                    lbl = "● Titan: online" if b == "Titan" else "● Ollama: online"
                    self.status_label.configure(text=lbl, text_color=self.colors["success"])
                    if b == "Ollama" and self.config.get("fetch_models") and not self._models_fetched:
                        self._models_fetched = True
                        self._refresh_models()
                else:
                    lbl = "● Titan: offline" if b == "Titan" else "● Ollama: offline"
                    self.status_label.configure(text=lbl, text_color=self.colors["error"])
                self._log(f"{b}: {'online' if ok else 'offline'}")

            self.after(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    def _start_monitors(self) -> None:
        self._check_connection()

        def _tick() -> None:
            self._update_hardware()
            self.after(self.hw_refresh_ms, _tick)

        self.after(500, _tick)

        def _conn_tick() -> None:
            self._check_connection()
            self.after(self.config["conn_check_ms"], _conn_tick)

        self.after(15000, _conn_tick)

        def _autosave_tick() -> None:
            save_memory(self.messages)
            self.after(self.config.get("memory_auto_save_interval", 30) * 1000, _autosave_tick)

        self.after(30_000, _autosave_tick)

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
            self.mic_btn.configure(state="disabled", text="...")
            self._log("Słucham...")

            def _listen() -> None:
                result = stt_listen(timeout=3, phrase_time_limit=15)
                def _done() -> None:
                    self.mic_btn.configure(state="normal", text="🎤")
                    if result:
                        self.input_entry.delete(0, "end")
                        self.input_entry.insert(0, result)
                        self._log(f"Transkrypcja: {result[:50]}...")
                    else:
                        self._log("Nie rozpoznano mowy.")
                self.after(0, _done)

            threading.Thread(target=_listen, daemon=True).start()
        except ImportError:
            self._log("STT: pip install SpeechRecognition PyAudio")

    def _on_send(self) -> None:
        text = self.input_entry.get().strip()
        if not text:
            return

        model = self.model_var.get()
        if not model:
            self._log("Wybierz model z listy.")
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
        self._log(f"Wysyłanie → {model}" + (" [Agent]" if use_agent else "") + "...")

        def _infer() -> None:
            try:
                from mobius_context import build_context
                history = build_context(self.messages, text)
            except ImportError:
                history = self.messages[-self.max_context :]
            prompt_lines = [
                f"{'Użytkownik' if m['role']=='user' else 'MOBIUS'}: {m['content']}"
                for m in history
            ]
            prompt_lines.append("MOBIUS:")
            prompt = "\n".join(prompt_lines)

            if use_agent:
                self._run_agent(prompt, text)
            else:
                self._run_streaming(prompt, text)

        threading.Thread(target=_infer, daemon=True).start()

    def _run_agent(self, prompt: str, user_text: str) -> None:
        """Tryb agenta — ReAct loop z narzędziami."""
        try:
            from mobius_agent import run_agent_loop

            backend = self.backend_var.get()
            allowed = self.config.get("agent_allowed_tools")
            recall = recall_context(user_text, n=self.config.get("memory_recall_n", 3))
            system = self._get_system_prompt()
            if recall:
                system = system + "\n\n## Kontekst z poprzednich sesji:\n" + recall
            system = system + "\n\nMasz dostęp do narzędzi. Używaj ich gdy potrzebne."

            def _generate(p: str, sys: str) -> str:
                if backend == "Titan":
                    try:
                        from mobius_titan_client import titan_infer
                        text, _ = titan_infer(
                            host=self.config.get("titan_host", "localhost"),
                            port=self.config.get("titan_port", 50051),
                            prompt=p,
                            system=sys,
                            model_id=self.config.get("titan_model", ""),
                            max_new_tokens=512,
                            timeout=self.config.get("titan_timeout", 300),
                        )
                        return text
                    except ImportError:
                        return "[Titan: pip install grpcio]"
                resp, _ = ollama_generate(
                    base_url=self.ollama_base,
                    model=self.model_var.get(),
                    prompt=p,
                    system=sys,
                    timeout=self.ollama_timeout,
                    temperature=self.config.get("temperature", 0.7),
                    top_p=self.config.get("top_p", 0.9),
                    num_predict=self.config.get("max_new_tokens", 512),
                )
                return resp

            response, steps = run_agent_loop(
                _generate, user_text, system,
                allowed_tools=allowed,
                max_steps=self.config.get("agent_max_steps", 5),
            )
            for s in steps:
                self.after(0, lambda msg=s: self._log(msg))

            def _done() -> None:
                self._append_message("assistant", response)
                self._log("Agent zakończony.")
                self.send_btn.configure(state="normal")
                self.mic_btn.configure(state="normal")
                self._notify("MOBIUS", "Agent zakończony.")
                if self.config.get("profile_auto_update", True) and response:
                    updated = update_profile_from_response(
                        response, self.profile, self._profile_generate_fn()
                    )
                    if updated != self.profile:
                        self.profile = updated
                        save_profile(self.profile)

            self.after(0, _done)
        except Exception as e:
            def _err() -> None:
                self._append_message("assistant", f"[Błąd agenta: {e}]")
                self.send_btn.configure(state="normal")
                self.mic_btn.configure(state="normal")
            self.after(0, _err)

    def _run_streaming(self, prompt: str, user_text: str) -> None:
        """Streaming — token po tokenie (Ollama lub Titan)."""
        start = time.perf_counter()
        full_response: list[str] = []
        backend = self.backend_var.get()
        recall = recall_context(user_text, n=self.config.get("memory_recall_n", 3))
        system = self._get_system_prompt()
        if recall:
            system = system + "\n\n## Kontekst z poprzednich sesji:\n" + recall

        def _stream() -> None:
            try:
                def _prefix() -> None:
                    self.chat_text.configure(state="normal")
                    self.chat_text.insert("end", "MOBIUS: ", "assistant")
                    self.chat_text.configure(state="disabled")
                self.after(0, _prefix)

                if backend == "Titan":
                    from mobius_titan_client import titan_infer_stream
                    stream_gen = titan_infer_stream(
                        host=self.config.get("titan_host", "localhost"),
                        port=self.config.get("titan_port", 50051),
                        prompt=prompt,
                        system=system,
                        model_id=self.config.get("titan_model", ""),
                        max_new_tokens=self.config.get("max_new_tokens", 512),
                        temperature=self.config.get("temperature", 0.7),
                        timeout=self.config.get("titan_timeout", 300),
                    )
                else:
                    stream_gen = ollama_generate_stream(
                        base_url=self.ollama_base,
                        model=self.model_var.get(),
                        prompt=prompt,
                        system=system,
                        timeout=self.ollama_timeout,
                        temperature=self.config.get("temperature", 0.7),
                        top_p=self.config.get("top_p", 0.9),
                        num_predict=self.config.get("max_new_tokens", 512),
                    )

                for token, done in stream_gen:
                    full_response.append(token)

                    def _update(t=token) -> None:
                        self.chat_text.configure(state="normal")
                        self.chat_text.insert("end", t, "assistant")
                        self.chat_text.see("end")
                        self.chat_text.configure(state="disabled")

                    self.after(0, _update)

                response = "".join(full_response)

                if not response and backend != "Titan":
                    resp_text, _ = ollama_generate(
                        self.ollama_base,
                        self.model_var.get(),
                        prompt,
                        system,
                        timeout=self.ollama_timeout,
                        temperature=self.config.get("temperature", 0.7),
                        top_p=self.config.get("top_p", 0.9),
                        num_predict=self.config.get("max_new_tokens", 512),
                    )
                    response = resp_text or response
                    def _fallback_update() -> None:
                        self.chat_text.configure(state="normal")
                        self.chat_text.insert("end", response, "assistant")
                        self.chat_text.see("end")
                        self.chat_text.configure(state="disabled")
                    self.after(0, _fallback_update)
                elapsed = time.perf_counter() - start

                def _done() -> None:
                    self._append_message("assistant", response, update_chat=False)
                    self.chat_text.configure(state="normal")
                    self.chat_text.insert("end", "\n\n", "assistant")
                    self.chat_text.configure(state="disabled")
                    self._log(f"Odpowiedź: {elapsed:.2f}s")
                    self.send_btn.configure(state="normal")
                    self.mic_btn.configure(state="normal")
                    self._notify("MOBIUS", "Odpowiedź gotowa.")
                    if self.config.get("profile_auto_update", True) and response:
                        updated = update_profile_from_response(
                            response, self.profile, self._profile_generate_fn()
                        )
                        if updated != self.profile:
                            self.profile = updated
                            save_profile(self.profile)

                self.after(0, _done)
            except Exception as e:
                def _err() -> None:
                    self._append_message("assistant", f"[Błąd: {e}]")
                    self.send_btn.configure(state="normal")
                    self.mic_btn.configure(state="normal")
                self.after(0, _err)

        threading.Thread(target=_stream, daemon=True).start()

    def on_closing(self) -> None:
        if self._wake_listener:
            self._wake_listener.stop()
        if self.config.get("memory_auto_index", True):
            auto_index_session(self.messages, self.session_id)
        save_memory(self.messages)
        if self._daemon:
            self._daemon.stop()
        self.destroy()


def main() -> None:
    app = MobiusGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
