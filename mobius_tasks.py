"""MOBIUS Task Queue — asynchroniczne zadania w tle z persystencją."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

MOBIUS_ROOT = Path(__file__).resolve().parent
TASKS_FILE = MOBIUS_ROOT / "tasks.json"


class TaskQueue:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="MobiusTask")
        self._lock = threading.Lock()
        self._tasks: dict[str, dict] = self._load_active()

    def _load_active(self) -> dict[str, dict]:
        if not TASKS_FILE.exists():
            return {}
        try:
            data = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            return {t["id"]: t for t in data if t.get("status") in ("pending", "running")}
        except Exception:
            return {}

    def _persist(self) -> None:
        try:
            with self._lock:
                snapshot = list(self._tasks.values())
            TASKS_FILE.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def add_task(self, name: str, fn: Callable[..., Any], *args: Any) -> str:
        task_id = str(uuid.uuid4())[:8]
        task: dict = {
            "id": task_id,
            "name": name,
            "status": "pending",
            "created": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }
        with self._lock:
            self._tasks[task_id] = task
        self._persist()
        self._executor.submit(self._run, task_id, fn, *args)
        return task_id

    def _run(self, task_id: str, fn: Callable, *args: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "running"
        self._persist()
        try:
            result = fn(*args)
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].update({"status": "done", "result": str(result)[:500]})
            name = self._tasks.get(task_id, {}).get("name", task_id)
            try:
                from mobius_events import get_bus, TASK_COMPLETED
                get_bus().publish(TASK_COMPLETED, {"id": task_id, "name": name, "result": result})
            except ImportError:
                pass
        except Exception as e:
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].update({"status": "failed", "error": str(e)})
        self._persist()

    def get_status(self, task_id: str) -> Optional[dict]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task["status"] == "pending":
                task.update({"status": "failed", "error": "cancelled"})
                return True
        return False

    def list_pending(self) -> list[dict]:
        with self._lock:
            return [t for t in self._tasks.values() if t["status"] in ("pending", "running")]


_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
