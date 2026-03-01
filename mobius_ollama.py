"""
MOBIUS Ollama — minimalna warstwa do Ollama API.
Bez zależności GUI (customtkinter, pynvml, matplotlib).
Używane przez mobius_gui i mobius_api.
"""

from __future__ import annotations

import json
import time
from typing import Generator

import requests


def ollama_available(base_url: str, timeout: float = 3) -> bool:
    try:
        return requests.get(f"{base_url}/api/tags", timeout=timeout).status_code == 200
    except Exception:
        return False


def ollama_fetch_models(base_url: str, timeout: float = 5) -> list[str]:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=timeout)
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
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
    num_ctx: int | None = None,
    num_gpu: int | None = None,
) -> Generator[tuple[str, bool], None, None]:
    url = f"{base_url.rstrip('/')}/api/generate"
    opts: dict = {"temperature": temperature, "top_p": top_p, "num_predict": num_predict}
    if num_ctx is not None:
        opts["num_ctx"] = num_ctx
    if num_gpu is not None and num_gpu >= 0:
        opts["num_gpu"] = num_gpu
    payload = {"model": model, "prompt": prompt, "system": system, "stream": True, "options": opts}
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
    except Exception:
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
    num_ctx: int | None = None,
    num_gpu: int | None = None,
) -> tuple[str, float]:
    url = f"{base_url.rstrip('/')}/api/generate"
    opts: dict = {"temperature": temperature, "top_p": top_p, "num_predict": num_predict}
    if num_ctx is not None:
        opts["num_ctx"] = num_ctx
    if num_gpu is not None and num_gpu >= 0:
        opts["num_gpu"] = num_gpu
    payload = {"model": model, "prompt": prompt, "system": system, "stream": False, "options": opts}
    last_error = None
    elapsed = 0.0
    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            elapsed = time.perf_counter() - start
            return r.json().get("response", "").strip(), elapsed
        except Exception as e:
            last_error = e
            elapsed = time.perf_counter() - start
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            err_str = str(e)
            if "Connection refused" in err_str or "10061" in err_str:
                return "[Ollama offline] Uruchom ollama serve.", elapsed
            if "timeout" in err_str.lower():
                return "[Timeout] Spróbuj krótszego zapytania.", elapsed
            return f"[Błąd: {e}]", elapsed
    return f"[Błąd: {last_error}]", elapsed
