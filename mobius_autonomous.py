"""
MOBIUS Autonomous Loop — Percepcja → Myślenie → Działanie → Uczenie się.
Cykl AGI: daemon zbiera kontekst, pyta LLM co zrobić, wykonuje akcję, zapisuje do pamięci.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

import requests

log = logging.getLogger("mobius_autonomous")

# Bezpieczne narzędzia dla autonomicznego trybu (bez run_shell, execute_script, write_file)
AUTONOMOUS_SAFE_TOOLS = [
    "add_reminder",
    "rag_add",
    "rag_search",
    "read_file",
    "list_dir",
    "get_active_window",
    "get_clipboard",
]


def _ollama_generate(
    base_url: str,
    model: str,
    prompt: str,
    system: str,
    timeout: float = 30,
    num_predict: int = 256,
    temperature: float = 0.3,
) -> str:
    """Minimalne wywołanie Ollama (bez zależności od mobius_gui)."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        log.warning("Ollama autonomous: %s", e)
        return ""


def generate_proactive_suggestion(
    config: dict,
    reminder_text: str,
    minutes_until: int,
) -> Optional[str]:
    """
    Zapytaj LLM o proaktywna sugestie dla nadchodzacego przypomnienia.
    Zwraca jedno zdanie (pytanie do uzytkownika) lub None.
    """
    if not config.get("proactive_enabled", True):
        return None
    base = config.get("ollama_host", "http://localhost:11434")
    models = config.get("default_models", ["qwen2.5:7b"])
    model = models[0] if models else "qwen2.5:7b"
    system = "Jestes MOBIUS. Odpowiedz jednym krotkim pytaniem po polsku (max 15 slow). Lub NONE jesli nic."
    prompt = f"Za {minutes_until} min: {reminder_text}. Jakie proaktywne pytanie zadasz uzytkownikowi? Np. 'Mam przygotowac notatki?'"
    resp = _ollama_generate(base, model, prompt, system, timeout=15, num_predict=80)
    if not resp or resp.upper().strip() == "NONE":
        return None
    return resp.strip()[:200]


def gather_context(config: dict) -> str:
    """Zbierz kontekst: przypomnienia, czas, opcjonalnie okno/schowek."""
    parts: list[str] = []
    now = datetime.now()
    parts.append(f"Czas: {now.strftime('%H:%M')}, {now.strftime('%A %d.%m.%Y')}")

    # Przypomnienia (nadchodzące i zaległe)
    try:
        from mobius_reminders import load_reminders, get_due_reminders
        due = get_due_reminders()
        if due:
            parts.append("Przypomnienia zaległe: " + "; ".join(due[:5]))
        all_r = load_reminders()
        upcoming = [r for r in all_r if r.get("when") and not _is_due(r.get("when", ""))][:3]
        if upcoming:
            parts.append("Przypomnienia nadchodzące: " + "; ".join(
                f"{r.get('text', '')} ({r.get('raw_when', r.get('when', ''))})" for r in upcoming
            ))
    except Exception as e:
        log.debug("Reminders context: %s", e)

    # Kontekst systemowy (jeśli włączony)
    if config.get("agent_system_context", False):
        try:
            from mobius_system import get_system_context
            ctx = get_system_context()
            if ctx.get("active_window") and ctx["active_window"].get("title"):
                parts.append(f"Aktywne okno: {ctx['active_window']['title']}")
            if ctx.get("running_apps"):
                parts.append("Aplikacje: " + ", ".join(ctx["running_apps"][:8]))
        except Exception:
            pass

    # Ostatnie wpisy z RAG (co użytkownik ostatnio dodawał)
    try:
        from mobius_rag import rag_search
        recent = rag_search("ostatnia sesja kontekst", n_results=2)
        if recent:
            parts.append("Ostatni kontekst z bazy wiedzy: " + " | ".join(recent[:2])[:300])
    except Exception:
        pass

    return "\n".join(parts)


def _is_due(when: str) -> bool:
    if not when or not str(when).strip():
        return True
    try:
        s = str(when).replace("Z", "+00:00")[:19]
        dt = datetime.fromisoformat(s)
        return datetime.now() >= dt
    except Exception:
        return True


def _execute_autonomous_action(action_str: str, allowed_tools: set[str]) -> Optional[str]:
    """Wykonaj pojedynczą akcję. Zwraca wynik lub None."""
    m = re.search(r"Action:\s*(\w+)\s*\((.*)\)", action_str, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    tool_name = m.group(1).strip().lower()
    args_str = m.group(2).strip()
    if tool_name not in allowed_tools:
        return f"Narzędzie niedozwolone: {tool_name}"
    try:
        from mobius_agent import execute_tool
        return execute_tool(action_str, allowed_tools)
    except Exception as e:
        return str(e)


def run_cycle(config: dict) -> Optional[dict[str, Any]]:
    """
    Jeden cykl autonomiczny: zbierz kontekst → zapytaj LLM → wykonaj akcję → zapisz.
    Zwraca {"action": str, "result": str, "context": str} lub None jeśli nic nie zrobiono.
    """
    if not config.get("autonomous_enabled", True):
        return None

    base = config.get("ollama_host", "http://localhost:11434")
    models = config.get("default_models", ["qwen2.5:7b"])
    model = models[0] if models else "qwen2.5:7b"
    allowed = config.get("autonomous_allowed_tools", AUTONOMOUS_SAFE_TOOLS)
    allowed_set = set(allowed)

    context = gather_context(config)
    if not context.strip():
        context = "Brak kontekstu."

    system = """Jesteś MOBIUS — autonomiczny asystent AGI. Cykl: Percepcja → Myślenie → Działanie.
Odpowiadaj WYŁĄCZNIE w formacie:
Action: nazwa_narzędzia("arg1", "arg2")
lub
NONE
jeśli nic nie trzeba robić. Jedna akcja na cykl. Bądź zwięzły."""

    tool_list = "\n".join(f"- {t}" for t in allowed_set)
    prompt = f"""Kontekst:
{context}

Dostępne narzędzia (użyj dokładnie tego formatu):
{tool_list}

Co zrobić? Odpowiedz Action: lub NONE."""

    response = _ollama_generate(base, model, prompt, system, timeout=25, num_predict=150)
    if not response:
        return None

    response_upper = response.upper().strip()
    if response_upper == "NONE" or response_upper.startswith("NONE"):
        return None

    result = _execute_autonomous_action(response, allowed_set)
    if result is None:
        return None

    # Zapisz wynik do RAG (uczenie się)
    try:
        from mobius_rag import rag_add
        meta = {
            "type": "autonomous",
            "timestamp": datetime.now().isoformat(),
            "action": response[:100],
        }
        rag_add(f"Autonomiczny cykl: {response[:80]} → {result[:200]}", meta)
    except Exception as e:
        log.debug("RAG save: %s", e)

    return {
        "action": response,
        "result": result,
        "context": context[:200],
    }
