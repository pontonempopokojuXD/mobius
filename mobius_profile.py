"""
MOBIUS User Profile — ekstrakcja i zarządzanie profilem użytkownika.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

MOBIUS_ROOT = Path(__file__).resolve().parent
USER_PROFILE_FILE = MOBIUS_ROOT / "user_profile.json"

_DEFAULTS: dict = {
    "name": "",
    "preferences": [],
    "facts": [],
    "last_updated": "",
}


def load_profile() -> dict:
    if not USER_PROFILE_FILE.exists():
        return _DEFAULTS.copy()
    try:
        with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except Exception:
        return _DEFAULTS.copy()


def save_profile(profile: dict) -> None:
    try:
        with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_profile_prompt() -> str:
    profile = load_profile()
    if not profile.get("name") and not profile.get("facts"):
        return ""
    lines = ["## Profil użytkownika"]
    name = profile.get("name", "")
    if name:
        lines.append(f"Imię: {name}")
    prefs = profile.get("preferences", [])
    if prefs:
        lines.append("Preferencje:")
        lines.extend(f"- {p}" for p in prefs)
    facts = profile.get("facts", [])
    if facts:
        lines.append("Znane fakty:")
        lines.extend(f"- {f}" for f in facts)
    return "\n".join(lines)


def _extract_llm(response: str, generate_fn: Callable[[str, str], str]) -> Optional[dict]:
    """Wyciągnij fakty z odpowiedzi przez LLM. Zwraca None przy błędzie."""
    prompt = (
        "Z poniższego tekstu wyciągnij TYLKO fakty o użytkowniku w formacie JSON.\n"
        'Pola: name (str|null), new_facts (list[str]), new_preferences (list[str]).\n'
        'Jeśli nic nie ma — zwróć {"name": null, "new_facts": [], "new_preferences": []}.\n'
        f"Tekst: {response[:500]}"
    )
    try:
        raw = generate_fn(prompt, "Odpowiedz tylko czystym JSON, bez markdown.")
        raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(raw)
        return {
            "name": data.get("name"),
            "new_facts": data.get("new_facts", []),
            "new_preferences": data.get("new_preferences", []),
        }
    except Exception:
        return None


def _extract_regex(response: str) -> dict:
    """Fallback regex extraction."""
    text_lower = response.lower()
    name: Optional[str] = None
    name_match = re.search(
        r"(?:nazywam się|jestem)\s+([A-ZŁÓŚŻŹĆŃĘĄ][a-zA-ZłóśżźćńęąĄŁÓŚŻŹĆŃÉ]+)",
        response,
    )
    if name_match:
        name = name_match.group(1)
    prefs = re.findall(r"(?:lubię|preferuję)\s+([^,.!?\n]{2,40})", text_lower)
    facts = re.findall(r"(?:mam|pracuję jako)\s+([^,.!?\n]{2,40})", text_lower)
    return {
        "name": name,
        "new_facts": [f.strip() for f in facts],
        "new_preferences": [p.strip() for p in prefs],
    }


def update_profile_from_response(
    response: str,
    current_profile: dict,
    generate_fn: Optional[Callable[[str, str], str]] = None,
) -> dict:
    profile = {**current_profile}

    extracted = _extract_llm(response, generate_fn) if generate_fn else None
    if extracted is None:
        extracted = _extract_regex(response)

    if extracted.get("name"):
        profile["name"] = extracted["name"]

    prefs: list[str] = list(profile.get("preferences", []))
    for p in extracted.get("new_preferences", []):
        p = p.strip()
        if p and p not in prefs:
            prefs.append(p)
    profile["preferences"] = prefs[:20]

    facts: list[str] = list(profile.get("facts", []))
    for f in extracted.get("new_facts", []):
        f = f.strip()
        if f and f not in facts:
            facts.append(f)
    profile["facts"] = facts[:30]

    if profile != current_profile:
        profile["last_updated"] = datetime.now().isoformat()

    return profile
