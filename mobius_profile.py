"""
MOBIUS User Profile — ekstrakcja i zarządzanie profilem użytkownika.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

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


def update_profile_from_response(response: str, current_profile: dict) -> dict:
    profile = {**current_profile}
    text_lower = response.lower()

    name_match = re.search(
        r"(?:nazywam się|jestem)\s+([A-ZŁÓŚŻŹĆŃĘĄ][a-zA-ZłóśżźćńęąĄŁÓŚŻŹĆŃÉ]+)",
        response,
    )
    if name_match:
        profile["name"] = name_match.group(1)

    pref_matches = re.findall(r"(?:lubię|preferuję)\s+([^,.!?\n]{2,40})", text_lower)
    prefs: list[str] = list(profile.get("preferences", []))
    for p in pref_matches:
        p = p.strip()
        if p and p not in prefs:
            prefs.append(p)
    profile["preferences"] = prefs[:20]

    fact_matches = re.findall(r"(?:mam|pracuję jako)\s+([^,.!?\n]{2,40})", text_lower)
    facts: list[str] = list(profile.get("facts", []))
    for f in fact_matches:
        f = f.strip()
        if f and f not in facts:
            facts.append(f)
    profile["facts"] = facts[:30]

    if profile != current_profile:
        profile["last_updated"] = datetime.now().isoformat()

    return profile
