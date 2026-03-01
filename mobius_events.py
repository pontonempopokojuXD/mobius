"""MOBIUS Event Bus — thread-safe pub/sub, singleton."""

from __future__ import annotations

import threading
from typing import Any, Callable

HARDWARE_ALERT = "hardware_alert"
REMINDER_DUE = "reminder_due"
TASK_COMPLETED = "task_completed"
AUTONOMOUS_ACTION = "autonomous_action"
PROACTIVE_SUGGESTION = "proactive_suggestion"
WAKE_WORD_DETECTED = "wake_word_detected"
MODEL_RESPONSE_READY = "model_response_ready"
AGENT_STEP = "agent_step"
USER_ACTIVE = "user_active"
USER_IDLE = "user_idle"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    def publish(self, event_type: str, data: Any = None) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
        for cb in callbacks:
            threading.Thread(target=cb, args=(data,), daemon=True).start()


_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
