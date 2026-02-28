"""
MOBIUS Przypomnienia — proaktywny harmonogram
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REMINDERS_FILE = Path(__file__).resolve().parent / "reminders.json"


def load_reminders() -> list[dict]:
    """Wczytaj przypomnienia."""
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_reminders(reminders: list[dict]) -> None:
    """Zapisz przypomnienia."""
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


def add_reminder(text: str, when: Optional[str] = None) -> str:
    """
    Dodaj przypomnienie.
    when: ISO datetime lub "za 1h", "jutro" — opcjonalne.
    """
    reminders = load_reminders()
    r = {"id": len(reminders) + 1, "text": text, "when": when or "", "created": datetime.now().isoformat()}
    reminders.append(r)
    save_reminders(reminders)
    return f"Dodano: {text}"


def get_due_reminders() -> list[str]:
    """Zwróć listę przypomnień do wyświetlenia (uproszczone — wszystkie aktywne)."""
    reminders = load_reminders()
    return [r["text"] for r in reminders[-10:] if r.get("text")]


def clear_reminder(reminder_id: int) -> bool:
    """Usuń przypomnienie po ID."""
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)
    return True
