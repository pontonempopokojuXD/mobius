"""MOBIUS System Integration — aktywne okno, schowek, kontekst systemowy."""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Optional

_PYGETWINDOW = False
try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except ImportError:
    pass

_PSUTIL = False
try:
    import psutil
    _PSUTIL = True
except ImportError:
    pass


def get_active_window() -> Optional[dict]:
    if not _PYGETWINDOW:
        return None
    try:
        win = gw.getActiveWindow()
        if not win:
            return None
        title = win.title or ""
        process = ""
        if _PSUTIL and title:
            try:
                for proc in psutil.process_iter(["name", "pid"]):
                    if proc.info["name"] and proc.info["name"].lower() in title.lower():
                        process = proc.info["name"]
                        break
            except Exception:
                pass
        return {"title": title, "process": process, "pid": 0}
    except Exception:
        return None


def get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except ImportError:
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip()
        except Exception:
            return ""


def set_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError:
        try:
            escaped = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{escaped}'"],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False


def list_running_apps() -> list[str]:
    if not _PSUTIL:
        return []
    try:
        names = {p.info["name"] for p in psutil.process_iter(["name"]) if p.info.get("name")}
        return sorted(names)[:50]
    except Exception:
        return []


def get_system_context() -> dict:
    now = datetime.now()
    return {
        "active_window": get_active_window(),
        "running_apps": list_running_apps()[:20],
        "time": now.strftime("%H:%M"),
        "day": now.strftime("%A"),
    }
