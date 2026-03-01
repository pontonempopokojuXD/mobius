"""
MOBIUS HTTP API — n8n / integracja zewnętrzna
"""

from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify

CONFIG_FILE = Path(__file__).resolve().parent / "mobius_config.json"
MOBIUS_ROOT = Path(__file__).resolve().parent

app = Flask(__name__)
VERSION = "1.0"
_API_HOST = "127.0.0.1"  # ustawiane przy starcie


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_ollama_host() -> str:
    cfg = _load_config()
    return cfg.get("ollama", {}).get("host", "http://localhost:11434").rstrip("/")


def _get_model(req_data: dict) -> str:
    cfg = _load_config()
    defaults = cfg.get("ollama", {}).get("default_models", ["qwen2.5:7b"])
    return req_data.get("model", defaults[0] if defaults else "qwen2.5:7b")


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cfg = _load_config()
        token = cfg.get("api", {}).get("auth_token", "")
        if token and request.headers.get("X-MOBIUS-TOKEN") != token:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


SYSTEM = "Jesteś MOBIUS — lapidarny, konkretny asystent AI."


@app.route("/ask", methods=["POST"])
@require_token
def ask():
    try:
        from mobius_ollama import ollama_generate
        data = request.get_json() or {}
        prompt = data.get("prompt", "")
        model = _get_model(data)
        start = time.perf_counter()
        resp, _ = ollama_generate(_get_ollama_host(), model, prompt, SYSTEM, timeout=90)
        elapsed = time.perf_counter() - start
        return jsonify({"response": resp, "elapsed_s": round(elapsed, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/agent", methods=["POST"])
@require_token
def agent():
    try:
        from mobius_ollama import ollama_generate
        from mobius_agent import run_agent_loop
        data = request.get_json() or {}
        prompt = data.get("prompt", "")
        model = _get_model(data)
        cfg = _load_config()
        allowed = cfg.get("agent", {}).get("allowed_tools", [])

        def _generate(p: str, sys: str) -> str:
            r, _ = ollama_generate(_get_ollama_host(), model, p, sys, timeout=90)
            return r

        start = time.perf_counter()
        response, steps = run_agent_loop(_generate, prompt, SYSTEM, allowed_tools=allowed or None)
        elapsed = time.perf_counter() - start
        return jsonify({"response": response, "steps": steps, "elapsed_s": round(elapsed, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reminder", methods=["POST"])
@require_token
def reminder():
    try:
        from mobius_reminders import add_reminder
        data = request.get_json() or {}
        text = data.get("text", "")
        when = data.get("when", "")
        msg = add_reminder(text, when or None)
        return jsonify({"status": "ok", "message": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reminders", methods=["GET"])
@require_token
def reminders():
    try:
        from mobius_reminders import load_reminders
        return jsonify({"reminders": load_reminders()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/status", methods=["GET"])
@require_token
def status():
    try:
        from mobius_ollama import ollama_available
        host = _get_ollama_host()
        return jsonify({
            "ollama": ollama_available(host),
            "model": _get_model({}),
            "version": VERSION,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rag/add", methods=["POST"])
@require_token
def rag_add():
    try:
        from mobius_rag import rag_add as rag_add_fn
        data = request.get_json() or {}
        text = data.get("text", "")
        ok = rag_add_fn(text)
        return jsonify({"status": "ok" if ok else "error"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rag/search", methods=["POST"])
@require_token
def rag_search():
    try:
        from mobius_rag import rag_search as rag_search_fn
        data = request.get_json() or {}
        query = data.get("query", "")
        n = int(data.get("n", 5))
        results = rag_search_fn(query, n)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _task_endpoint_allowed() -> bool:
    """Endpoint /task wymaga auth_token gdy API wystawione na sieć (RCE)."""
    cfg = _load_config()
    token = cfg.get("api", {}).get("auth_token", "")
    if token:
        return True
    if _API_HOST in ("127.0.0.1", "localhost", ""):
        return True
    return False


@app.route("/task", methods=["POST"])
@require_token
def task():
    if not _task_endpoint_allowed():
        return jsonify({"error": "Endpoint /task wymaga api.auth_token gdy API na 0.0.0.0"}), 403
    try:
        from mobius_tasks import get_task_queue
        import subprocess
        data = request.get_json() or {}
        name = data.get("name", "task")
        command = data.get("command", "")

        def _run() -> str:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=300, cwd=str(MOBIUS_ROOT),
            )
            return (r.stdout or "") + (r.stderr or "")

        task_id = get_task_queue().add_task(name, _run)
        return jsonify({"task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/task/<task_id>", methods=["GET"])
@require_token
def task_status(task_id: str):
    try:
        from mobius_tasks import get_task_queue
        t = get_task_queue().get_status(task_id)
        if not t:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"id": t["id"], "status": t["status"], "result": t.get("result")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    _API_HOST = args.host
    print(f"MOBIUS API -> http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
