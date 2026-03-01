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
    next_id = max((r.get("id", 0) for r in reminders), default=0) + 1
    r = {
        "id": next_id,
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


def _get_due_reminder_ids() -> list[tuple[int, str]]:
    """Zwraca listę (id, text) dla przypomnień zaległych."""
    reminders = load_reminders()
    return [
        (r["id"], r["text"])
        for r in reminders
        if r.get("id") and r.get("text") and _is_due(r.get("when", ""))
    ][-10:]


def get_upcoming_reminders(within_minutes: int = 15) -> list[dict]:
    """
    Przypomnienia, ktore beda due w ciagu N minut (ale jeszcze nie sa).
    Zwraca list[{text, when, minutes_until}]. Pomija te z proactive_fired=True.
    """
    reminders = load_reminders()
    now = datetime.now()
    result = []
    for r in reminders:
        if r.get("proactive_fired"):
            continue
        when = r.get("when", "")
        if not when or not when.strip():
            continue
        try:
            dt = datetime.fromisoformat(when.replace("Z", "")[:19])
            if dt <= now:
                continue
            delta = (dt - now).total_seconds() / 60
            if 0 < delta <= within_minutes:
                result.append({
                    "text": r.get("text", ""),
                    "when": when,
                    "minutes_until": int(delta),
                    "id": r.get("id"),
                })
        except (ValueError, TypeError):
            continue
    return sorted(result, key=lambda x: x["minutes_until"])[:5]


def mark_proactive_fired(reminder_id: int) -> None:
    """Oznacz przypomnienie jako proactive_fired."""
    reminders = load_reminders()
    for r in reminders:
        if r.get("id") == reminder_id:
            r["proactive_fired"] = True
            break
    save_reminders(reminders)


def clear_reminder(reminder_id: int) -> bool:
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)
    return True
