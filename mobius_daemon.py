"""
MOBIUS Proactive Daemon — monitorowanie zasobów i przypomnień w tle.
"""

from __future__ import annotations

import logging
import threading

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

        while not self._stop.wait(interval):
            try:
                self._check_reminders()
                self._check_hardware(cpu_th, ram_th, cpu_sustained)
            except Exception as e:
                log.exception("Daemon error: %s", e)

    def _check_reminders(self) -> None:
        try:
            from mobius_events import REMINDER_DUE
            from mobius_reminders import get_due_reminders, load_reminders, save_reminders
            due = get_due_reminders()
            if not due:
                return
            all_reminders = load_reminders()
            fired: set[str] = set()
            for text in due:
                self._publish(REMINDER_DUE, text)
                fired.add(text)
            all_reminders = [r for r in all_reminders if r.get("text") not in fired]
            save_reminders(all_reminders)
        except Exception as e:
            log.warning("Reminder check error: %s", e)

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
                    self._publish(HARDWARE_ALERT, f"⚠️ CPU wysoki od 3 minut: {cpu:.0f}%")
                    self._cpu_high_count = 0
            else:
                self._cpu_high_count = 0

            if ram > ram_th:
                self._ram_high_count += 1
                if self._ram_high_count >= cpu_sustained:
                    self._publish(HARDWARE_ALERT, f"⚠️ RAM wysoki od 3 minut: {ram:.0f}%")
                    self._ram_high_count = 0
            else:
                self._ram_high_count = 0
        except Exception as e:
            log.warning("Hardware check error: %s", e)
