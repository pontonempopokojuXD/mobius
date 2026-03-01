"""
Smoke testy dla mobius_agent.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestAgent(unittest.TestCase):
    def test_import(self):
        from mobius_agent import (
            execute_tool,
            extract_final_answer,
            run_agent_loop,
            TOOLS,
            _build_tool_descriptions,
        )
        self.assertIsNotNone(execute_tool)
        self.assertIsNotNone(extract_final_answer)
        self.assertGreater(len(TOOLS), 0)

    def test_extract_final_answer_found(self):
        from mobius_agent import extract_final_answer
        text = "Thought: done\nFinal Answer: To jest odpowiedz."
        self.assertEqual(extract_final_answer(text), "To jest odpowiedz.")

    def test_extract_final_answer_not_found(self):
        from mobius_agent import extract_final_answer
        self.assertIsNone(extract_final_answer("Action: read_file(\"x\")"))
        self.assertIsNone(extract_final_answer(""))

    def test_execute_tool_read_file(self):
        from mobius_agent import execute_tool
        result = execute_tool(
            'Action: read_file("mobius_config.json")',
            {"read_file"}
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_execute_tool_list_dir(self):
        from mobius_agent import execute_tool
        result = execute_tool(
            'Action: list_dir(".")',
            {"list_dir"}
        )
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_execute_tool_invalid_returns_none(self):
        from mobius_agent import execute_tool
        self.assertIsNone(execute_tool("NONE", set()))
        self.assertIsNone(execute_tool("Final Answer: x", set()))

    def test_execute_tool_unknown_tool(self):
        from mobius_agent import execute_tool
        result = execute_tool('Action: nieistniejace("x")', set())
        self.assertIn("nieznane", result.lower())

    def test_build_tool_descriptions(self):
        from mobius_agent import _build_tool_descriptions
        desc = _build_tool_descriptions(["read_file", "list_dir"])
        self.assertIn("read_file", desc)
        self.assertIn("list_dir", desc)
        self.assertIn("Final Answer", desc)

    def test_run_agent_loop_with_mock_generate(self):
        from mobius_agent import run_agent_loop

        def mock_gen(prompt: str, system: str) -> str:
            return "Final Answer: Testowa odpowiedz."

        answer, steps = run_agent_loop(
            mock_gen,
            "Test query",
            "System",
            max_steps=3,
            allowed_tools=["read_file"],
        )
        self.assertEqual(answer, "Testowa odpowiedz.")
        self.assertEqual(len(steps), 1)


if __name__ == "__main__":
    unittest.main()
