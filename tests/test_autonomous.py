"""
Smoke testy dla mobius_autonomous.
"""

import sys
import unittest
from pathlib import Path

# Dodaj root projektu do path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestAutonomous(unittest.TestCase):
    def test_import(self):
        from mobius_autonomous import (
            gather_context,
            run_cycle,
            AUTONOMOUS_SAFE_TOOLS,
            _is_due,
            _execute_autonomous_action,
        )
        self.assertIsNotNone(gather_context)
        self.assertIsNotNone(run_cycle)
        self.assertGreater(len(AUTONOMOUS_SAFE_TOOLS), 0)

    def test_gather_context_returns_string(self):
        from mobius_autonomous import gather_context
        config = {
            "agent_system_context": False,
            "ollama_host": "http://localhost:11434",
        }
        ctx = gather_context(config)
        self.assertIsInstance(ctx, str)
        self.assertIn("Czas:", ctx)

    def test_gather_context_minimal(self):
        from mobius_autonomous import gather_context
        config = {}
        ctx = gather_context(config)
        self.assertTrue(len(ctx) > 0)
        self.assertTrue(ctx.strip() != "")

    def test_is_due_empty_returns_true(self):
        from mobius_autonomous import _is_due
        self.assertTrue(_is_due(""))
        self.assertTrue(_is_due(None))

    def test_is_due_future_returns_false(self):
        from mobius_autonomous import _is_due
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(days=1)).isoformat()
        self.assertFalse(_is_due(future))

    def test_is_due_past_returns_true(self):
        from mobius_autonomous import _is_due
        from datetime import datetime, timedelta
        past = (datetime.now() - timedelta(days=1)).isoformat()
        self.assertTrue(_is_due(past))

    def test_execute_action_none_for_invalid(self):
        from mobius_autonomous import _execute_autonomous_action
        result = _execute_autonomous_action("NONE", set())
        self.assertIsNone(result)
        result = _execute_autonomous_action("Final Answer: nic", set())
        self.assertIsNone(result)

    def test_execute_action_list_dir(self):
        from mobius_autonomous import _execute_autonomous_action
        result = _execute_autonomous_action(
            'Action: list_dir(".")',
            {"list_dir"}
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_execute_action_disallowed_returns_error(self):
        from mobius_autonomous import _execute_autonomous_action
        result = _execute_autonomous_action(
            'Action: run_shell("dir")',
            {"list_dir", "read_file"}
        )
        self.assertIn("niedozwolone", result.lower())

    def test_run_cycle_disabled_returns_none(self):
        from mobius_autonomous import run_cycle
        config = {"autonomous_enabled": False}
        result = run_cycle(config)
        self.assertIsNone(result)

    def test_run_cycle_with_ollama_offline_returns_none_or_result(self):
        from mobius_autonomous import run_cycle
        config = {
            "autonomous_enabled": True,
            "ollama_host": "http://localhost:11434",
            "default_models": ["qwen2.5:7b"],
            "autonomous_allowed_tools": ["add_reminder", "rag_add", "rag_search"],
        }
        result = run_cycle(config)
        # Moze byc None (Ollama offline lub LLM powiedzial NONE) lub dict
        if result is not None:
            self.assertIn("action", result)
            self.assertIn("result", result)


if __name__ == "__main__":
    unittest.main()
