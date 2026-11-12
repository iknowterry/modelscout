"""Settings-command parsing: only recognised settings are commands.

A delegated goal such as "ModelScout: rename the field…" must run as a normal
prompt, never be blocked as a settings command.
Run: python3 -m unittest discover tests
"""
import importlib.util
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "modelscout"
sys.path.insert(0, str(PLUGIN / "hooks"))
import proactive_check as pc  # noqa: E402


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "modelscout_hermes_plugin", PLUGIN / "__init__.py", submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Commands(unittest.TestCase):
    def test_settings_are_commands(self):
        for p, want in [("modelscout: status", "status"), ("ModelScout: auto", "auto"),
                        ("modelscout: ask mode", "ask"), ("modelscout: T1 stay", "t1 stay"),
                        ("modelscout: always switch for T3", "always switch for t3"),
                        ("modelscout: savings", "savings"), ("modelscout:", "")]:
            with self.subTest(prompt=p):
                self.assertEqual(pc.parse_command(p), want)

    def test_delegated_goals_are_not_commands(self):
        for p in ["ModelScout: rename the user_id field across all files",
                  "ModelScout: debug the race condition in the queue worker",
                  "modelscout: which model should I use for this?",
                  "refactor the auth module"]:
            with self.subTest(prompt=p):
                self.assertIsNone(pc.parse_command(p))

    def test_hermes_hook_runs_delegated_goal(self):
        out = load_plugin()._on_pre_llm_call(
            user_message="ModelScout: rename the user_id field across all files", model="x")
        self.assertTrue(out is None or "context" in out, out)
        self.assertNotIn("action", out or {})

    def test_delegated_child_gets_no_card(self):
        plugin = load_plugin()
        plugin._on_subagent_start(child_session_id="child-1", child_goal="ModelScout: rename x")
        self.assertIsNone(plugin._on_pre_llm_call(
            user_message="ModelScout: rename the user_id field across all files",
            model="x", session_id="child-1"))
        self.assertIn("context", plugin._on_pre_llm_call(
            user_message="rename the user_id field across all files", model="x", session_id="parent"))


if __name__ == "__main__":
    unittest.main()
