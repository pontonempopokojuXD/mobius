"""
MOBIUS Przypomnienia — proaktywny harmonogram
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REMINDERS_FILE = Path(__file__).resolve().parent / "reminders.json"

_DATEPARSER_AVAILABLE = False
try:
    import dateparser
    _DATEPARSER_AVAILABLE = True
except ImportError:
    pass


def load_reminders() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_reminders(reminders: list[dict]) -> None:
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


def _parse_when(when: str) -> str:
    """Parsuje naturalny czas → ISO string lub '' jeśli nie można."""
    if not when or not when.strip():
        return ""
    try:
        datetime.fromisoformat(when)
        return when
    except (ValueError, TypeError):
        pass
    if _DATEPARSER_AVAILABLE:
        try:
            parsed = dateparser.parse(
                when,
                languages=["pl", "en"],
                settings={
                    "PREFER_DATES_FROM": "future",
                    "RETURN_AS_TIMEZONE_AWARE": False,
                    "RELATIVE_BASE": datetime.now(),
                },
            )
            if parsed:
                return parsed.isoformat()
        except Exception:
            pass
    return ""


def _is_due(when: str) -> bool:
    """Czy przypomnienie jest już aktualne."""
    if not when or not when.strip():
        return True
    try:
        dt = datetime.fromisoformat(when)
        return datetime.now() >= dt
    except (ValueError, TypeError):
        return False


def add_reminder(text: str, when: Optional[str] = None) -> str:
    reminders = load_reminders()
    raw_when = when or ""
    parsed = _parse_when(raw_when)
    r = {
        "id": len(reminders) + 1,
        "text": text,
        "when": parsed,
        "raw_when": raw_when,
        "created": datetime.now().isoformat(),
    }
    reminders.append(r)
    save_reminders(reminders)
    when_info = f" ({raw_when})" if raw_when else ""
    return f"Dodano: {text}{when_info}"


def get_due_reminders() -> list[str]:
    reminders = load_reminders()
    return [r["text"] for r in reminders if r.get("text") and _is_due(r.get("when", ""))][-10:]


def clear_reminder(reminder_id: int) -> bool:
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)
    return True
