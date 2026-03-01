"""
MOBIUS Proactive Daemon — monitorowanie zasobów, przypomnień i autonomiczny cykl AGI.
"""

from __future__ import annotations

import logging
import threading
import time

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

log = logging.getLogger("mobius_daemon")


class ProactiveDaemon:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cpu_high_count = 0
        self._ram_high_count = 0
        self._last_autonomous = 0.0

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ProactiveDaemon")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _publish(self, event_type: str, data: object) -> None:
        try:
            from mobius_events import get_bus
            get_bus().publish(event_type, data)
        except ImportError:
            pass

    def _run(self) -> None:
        interval = self._config.get("daemon_interval_seconds", 60)
        cpu_sustained = self._config.get("daemon_cpu_sustained_checks", 3)
        cpu_th = self._config.get("cpu_alert", 90)
        ram_th = self._config.get("ram_alert", 95)
        autonomous_interval = self._config.get("autonomous_interval_seconds", 300)

        while not self._stop.wait(interval):
            try:
                self._check_reminders()
                self._check_proactive_reminders()
                self._check_hardware(cpu_th, ram_th, cpu_sustained)
                # Autonomiczny cykl AGI co N sekund
                if self._config.get("autonomous_enabled", True):
                    now = time.monotonic()
                    if now - self._last_autonomous >= autonomous_interval:
                        self._last_autonomous = now
                        self._run_autonomous_cycle()
            except Exception as e:
                log.exception("Daemon error: %s", e)

    def _run_autonomous_cycle(self) -> None:
        """Jeden cykl: Percepcja → Myślenie → Działanie → Uczenie się."""
        try:
            from mobius_autonomous import run_cycle
            from mobius_events import AUTONOMOUS_ACTION
            result = run_cycle(self._config)
            if result:
                self._publish(AUTONOMOUS_ACTION, result)
                log.info("Autonomous: %s → %s", result.get("action", "")[:60], result.get("result", "")[:80])
        except Exception as e:
            log.warning("Autonomous cycle: %s", e)

    def _check_reminders(self) -> None:
        try:
            from mobius_events import REMINDER_DUE
            from mobius_reminders import _get_due_reminder_ids, load_reminders, save_reminders
            due_ids = _get_due_reminder_ids()
            if not due_ids:
                return
            all_reminders = load_reminders()
            fired_ids: set[int] = set()
            for rid, text in due_ids:
                self._publish(REMINDER_DUE, text)
                fired_ids.add(rid)
            all_reminders = [r for r in all_reminders if r.get("id") not in fired_ids]
            save_reminders(all_reminders)
        except Exception as e:
            log.warning("Reminder check error: %s", e)

    def _check_proactive_reminders(self) -> None:
        """Przypomnienia za 5-15 min: zapytaj LLM o sugestie, wyslij powiadomienie."""
        if not self._config.get("proactive_enabled", True):
            return
        try:
            from mobius_events import PROACTIVE_SUGGESTION
            from mobius_autonomous import generate_proactive_suggestion
            from mobius_reminders import get_upcoming_reminders, mark_proactive_fired
            upcoming = get_upcoming_reminders(within_minutes=15)
            for r in upcoming:
                suggestion = generate_proactive_suggestion(
                    self._config, r["text"], r["minutes_until"]
                )
                msg = f"Za {r['minutes_until']} min: {r['text']}"
                if suggestion:
                    msg = f"{msg} {suggestion}"
                self._publish(PROACTIVE_SUGGESTION, {"message": msg, "reminder_id": r.get("id")})
                if r.get("id"):
                    mark_proactive_fired(r["id"])
                log.info("Proactive: %s", msg[:80])
                break
        except Exception as e:
            log.warning("Proactive check: %s", e)

    def _check_hardware(self, cpu_th: float, ram_th: float, cpu_sustained: int) -> None:
        if not _PSUTIL_AVAILABLE:
            return
        try:
            from mobius_events import HARDWARE_ALERT
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent

            if cpu > cpu_th:
                self._cpu_high_count += 1
                if self._cpu_high_count >= cpu_sustained:
                    self._publish(HARDWARE_ALERT, f"CPU wysoki od 3 minut: {cpu:.0f}%")
                    self._cpu_high_count = 0
            else:
                self._cpu_high_count = 0

            if ram > ram_th:
                self._ram_high_count += 1
                if self._ram_high_count >= cpu_sustained:
                    self._publish(HARDWARE_ALERT, f"RAM wysoki od 3 minut: {ram:.0f}%")
                    self._ram_high_count = 0
            else:
                self._ram_high_count = 0
        except Exception as e:
            log.warning("Hardware check error: %s", e)
