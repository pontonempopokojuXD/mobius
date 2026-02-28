"""
MOBIUS Agent — ReAct loop z narzędziami
Autonomiczny agent w stylu JARVIS/FRIDAY: myśl → działaj → obserwuj.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

MOBIUS_ROOT = Path(__file__).resolve().parent

# ─────────────────────────────────────────────────────────────────────────────
#  Narzędzia (Tools)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DESCRIPTIONS = """
Dostępne narzędzia (używaj formatu Action: nazwa(arg1, arg2)):
- read_file(path) — odczytaj zawartość pliku tekstowego
- write_file(path, content) — zapisz tekst do pliku
- list_dir(path) — listuj pliki w katalogu
- run_shell(command) — wykonaj polecenie w PowerShell/CMD
- execute_script(script_name, *args) — uruchom skrypt Python z folderu mobius
- add_reminder(text, when) — dodaj przypomnienie (when opcjonalne: "za 1h", "jutro")
- rag_search(query, n) — wyszukaj w bazie wiedzy (n=5 domyślnie)
- rag_add(text) — dodaj fragment do bazy wiedzy
- rag_add_file(path) — dodaj plik do bazy wiedzy

Gdy masz odpowiedź dla użytkownika, zakończ: Final Answer: <odpowiedź>
"""


def tool_read_file(path: str) -> str:
    """Odczytaj plik. path względem mobius lub absolutny."""
    p = Path(path)
    if not p.is_absolute():
        p = MOBIUS_ROOT / path
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Błąd: {e}]"


def tool_write_file(path: str, content: str) -> str:
    """Zapisz do pliku."""
    p = Path(path)
    if not p.is_absolute():
        p = MOBIUS_ROOT / path
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Zapisano: {p}"
    except Exception as e:
        return f"[Błąd: {e}]"


def tool_list_dir(path: str) -> str:
    """Listuj katalog."""
    p = Path(path) if path else MOBIUS_ROOT
    if not p.is_absolute():
        p = MOBIUS_ROOT / path
    try:
        items = list(p.iterdir())
        return "\n".join(f"{'[DIR]' if x.is_dir() else ''} {x.name}" for x in sorted(items)[:50])
    except Exception as e:
        return f"[Błąd: {e}]"


def tool_run_shell(command: str) -> str:
    """Wykonaj polecenie shell (PowerShell na Windows)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(MOBIUS_ROOT),
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip() or f"(exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return "Timeout (60s)"
    except Exception as e:
        return str(e)


def tool_execute_script(script_name: str, *args: str) -> str:
    """Uruchom skrypt Python z mobius."""
    script_path = MOBIUS_ROOT / script_name
    if not script_path.exists():
        return f"Skrypt nie istnieje: {script_path}"
    try:
        result = subprocess.run(
            ["python", str(script_path), *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(MOBIUS_ROOT),
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip() or f"(exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return "Timeout (120s)"
    except Exception as e:
        return str(e)


def tool_add_reminder(text: str, when: str = "") -> str:
    """Dodaj przypomnienie."""
    try:
        from mobius_reminders import add_reminder
        return add_reminder(text, when or None)
    except ImportError:
        return "Moduł reminders niedostępny"


def tool_rag_search(query: str, n: str = "5") -> str:
    """Wyszukaj w bazie wiedzy."""
    try:
        from mobius_rag import rag_search
        n_int = int(n) if n.isdigit() else 5
        results = rag_search(query, n_int)
        return "\n---\n".join(results) if results else "Brak wyników."
    except ImportError:
        return "RAG niedostępny: pip install chromadb"


def tool_rag_add(text: str) -> str:
    """Dodaj do bazy wiedzy."""
    try:
        from mobius_rag import rag_add
        return "Dodano." if rag_add(text) else "Błąd dodawania."
    except ImportError:
        return "RAG niedostępny: pip install chromadb"


def tool_rag_add_file(path: str) -> str:
    """Dodaj plik do bazy wiedzy."""
    try:
        from mobius_rag import rag_add_from_file
        n, msg = rag_add_from_file(path)
        return msg
    except ImportError:
        return "RAG niedostępny: pip install chromadb"


TOOLS: dict[str, Callable[..., str]] = {
    "read_file": lambda path: tool_read_file(path),
    "write_file": lambda path, content: tool_write_file(path, content),
    "list_dir": lambda path="": tool_list_dir(path),
    "run_shell": lambda command: tool_run_shell(command),
    "execute_script": lambda name, *a: tool_execute_script(name, *a),
    "add_reminder": lambda text, when="": tool_add_reminder(text, when),
    "rag_search": lambda q, n="5": tool_rag_search(q, n),
    "rag_add": lambda text: tool_rag_add(text),
    "rag_add_file": lambda path: tool_rag_add_file(path),
}


def execute_tool(action_str: str, allowed_tools: Optional[set[str]] = None) -> Optional[str]:
    """
    Parsuj Action: tool(args) i wykonaj.
    allowed_tools: jeśli podane, tylko te narzędzia dozwolone.
    """
    # Action: read_file("path") lub Action: run_shell("cmd")
    m = re.search(r"Action:\s*(\w+)\s*\((.*)\)", action_str, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    tool_name = m.group(1).strip().lower()
    args_str = m.group(2).strip()
    if tool_name not in TOOLS:
        return f"Narzędzie nieznane: {tool_name}"
    if allowed_tools is not None and tool_name not in allowed_tools:
        return f"Narzędzie niedozwolone: {tool_name}. Włącz w mobius_config.json → agent.allowed_tools"
    # Parsuj argumenty — obsługa "a", "b" oraz "a, b" w content
    args = []
    for match in re.finditer(r'"((?:[^"\\]|\\.)*)"|([^,\s]+)', args_str):
        g = match.group(1) or (match.group(2) if match.group(2) else None)
        if g is not None and g.strip():
            args.append(g.strip())
    args = [a.strip('"') for a in args if a]
    try:
        return TOOLS[tool_name](*args)
    except TypeError as e:
        return f"Błąd argumentów: {e}"


def extract_final_answer(text: str) -> Optional[str]:
    """Wyciągnij Final Answer: z odpowiedzi modelu."""
    m = re.search(r"Final\s+Answer:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


_TOOL_SIGS: dict[str, str] = {
    "read_file": "read_file(path)",
    "write_file": "write_file(path, content)",
    "list_dir": "list_dir(path)",
    "run_shell": "run_shell(command)",
    "execute_script": "execute_script(name, *args)",
    "add_reminder": "add_reminder(text, when)",
    "rag_search": "rag_search(query, n)",
    "rag_add": "rag_add(text)",
    "rag_add_file": "rag_add_file(path)",
}


def _build_tool_descriptions(allowed: Optional[list[str]] = None) -> str:
    """Buduj opis narzędzi (tylko dozwolone)."""
    tools = set(allowed) if allowed else set(TOOLS.keys())
    available = [t for t in TOOLS if t in tools]
    if not available:
        return "Brak dostępnych narzędzi.\nFinal Answer: <odpowiedź> gdy gotowe."
    lines = ["Dostępne narzędzia (Action: nazwa(arg1, arg2)):"]
    for t in available:
        lines.append(f"- {_TOOL_SIGS.get(t, t)}")
    lines.append("Final Answer: <odpowiedź> gdy gotowe.")
    return "\n".join(lines)


def run_agent_loop(
    generate_fn: Callable[[str, str], str],
    user_query: str,
    system_prompt: str,
    max_steps: int = 5,
    allowed_tools: Optional[list[str]] = None,
) -> tuple[str, list[str]]:
    """
    ReAct loop: Thought → Action → Observation → ...
    allowed_tools: lista dozwolonych (domyślnie wszystkie oprócz run_shell, execute_script).
    """
    steps: list[str] = []
    allowed_set = set(allowed_tools) if allowed_tools else set(TOOLS.keys())
    tool_desc = _build_tool_descriptions(allowed_tools)
    prompt = f"""Użytkownik: {user_query}

{tool_desc}

Zacznij od Thought:, potem Action: lub Final Answer:"""

    for step in range(max_steps):
        response = generate_fn(prompt, system_prompt)
        steps.append(f"Step {step + 1}: {response[:200]}...")

        final = extract_final_answer(response)
        if final:
            return final, steps

        action_result = execute_tool(response, allowed_set)
        if action_result is None:
            # Model nie wywołał Action — traktuj całość jako odpowiedź
            return response.strip(), steps

        prompt = f"{prompt}\n\nMOBIUS: {response}\n\nObservation: {action_result}\n\nMOBIUS:"
        if len(prompt) > 8000:
            prompt = prompt[-8000:]

    return "[Max steps reached. Odpowiedź niekompletna.]", steps
