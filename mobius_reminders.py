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


def _is_due(when: str) -> bool:
    """Czy przypomnienie jest już aktualne (when minęło lub puste)."""
    if not when or not when.strip():
        return True
    try:
        when_clean = when.strip().replace(" ", "T")
        if "+" in when_clean or when_clean.endswith("Z"):
            when_clean = when_clean.split("+")[0].rstrip().rstrip("Z").rstrip()
        if "T" in when_clean and len(when_clean) > 10:
            dt = datetime.fromisoformat(when_clean)
            return datetime.now() >= dt
        if len(when_clean) >= 10:
            dt = datetime.strptime(when_clean[:10], "%Y-%m-%d")
            return datetime.now().date() >= dt.date()
        return True
    except (ValueError, TypeError):
        return True


def get_due_reminders() -> list[str]:
    """Zwróć przypomnienia, których when już minął (lub puste = zawsze aktualne)."""
    reminders = load_reminders()
    return [r["text"] for r in reminders if r.get("text") and _is_due(r.get("when", ""))][-10:]


def clear_reminder(reminder_id: int) -> bool:
    """Usuń przypomnienie po ID."""
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)
    return True
