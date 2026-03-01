"""
Smoke testy dla mobius_rag i mobius_reminders.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestRAG(unittest.TestCase):
    def test_import(self):
        from mobius_rag import rag_add, rag_search
        self.assertIsNotNone(rag_add)
        self.assertIsNotNone(rag_search)

    def test_rag_add_returns_bool(self):
        from mobius_rag import rag_add
        result = rag_add("Test smoke " + __file__, {"test": True})
        self.assertIsInstance(result, bool)

    def test_rag_search_returns_list(self):
        from mobius_rag import rag_search
        result = rag_search("test smoke", n_results=3)
        self.assertIsInstance(result, list)


class TestReminders(unittest.TestCase):
    def test_import(self):
        from mobius_reminders import add_reminder, get_due_reminders, load_reminders
        self.assertIsNotNone(add_reminder)
        self.assertIsNotNone(get_due_reminders)

    def test_add_reminder_returns_string(self):
        from mobius_reminders import add_reminder, load_reminders, save_reminders
        result = add_reminder("Test smoke reminder", None)
        self.assertIsInstance(result, str)
        self.assertIn("Dodano", result)
        # Usun dodany reminder z pliku
        reminders = load_reminders()
        reminders = [r for r in reminders if "Test smoke reminder" not in r.get("text", "")]
        save_reminders(reminders)

    def test_get_due_reminders_returns_list(self):
        from mobius_reminders import get_due_reminders
        result = get_due_reminders()
        self.assertIsInstance(result, list)

    def test_get_upcoming_reminders_returns_list(self):
        from mobius_reminders import get_upcoming_reminders
        result = get_upcoming_reminders(within_minutes=60)
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
