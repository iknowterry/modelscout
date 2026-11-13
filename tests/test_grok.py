"""Grok Build host (beta): host detection, the rules file, picks, hook no-ops.
Payloads follow the Grok Build hook docs (camelCase keys, GROK_SESSION_ID env).
Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "modelscout"
HOOKS = PLUGIN / "hooks"
sys.path.insert(0, str(HOOKS))
import proactive_check as pc  # noqa: E402

CATALOG = {
    "xai": {"models": {
        "grok-4.3": {"cost": {"output": 2.5}, "release_date": "2026-04-17", "tool_call": True},
        "grok-4.7": {"cost": {"output": 6}, "release_date": "2026-09-21", "tool_call": True},
        "grok-4.20-0309-reasoning": {"cost": {"output": 2.5}, "release_date": "2026-03-09", "tool_call": True},
        "grok-build-0.1": {"cost": {"output": 2}, "release_date": "2026-04-16", "tool_call": True},
        "grok-imagine-image": {"release_date": "2026-01-28"},
    }},
    "anthropic": {"models": {"claude-haiku-5-5": {"cost": {"output": 5}, "release_date": "2026-10-01"}}},
}
for i in range(10):
    CATALOG[f"p{i}"] = {"models": {}}


class GrokHome(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "model-catalog.json").write_text(json.dumps(CATALOG))
        self.env = {"HOME": str(self.home), "GROK_HOME": str(self.home / ".grok"),
                    "HERMES_HOME": str(self.home / ".hermes")}
        self.patches = [mock.patch.dict(os.environ, self.env),
                        mock.patch.object(pc.catalog, "CLAUDE_CATALOG", self.home / ".claude" / "model-catalog.json"),
                        mock.patch.object(pc.prefs, "PROFILE", self.home / ".claude" / "modelscout-profile.json", create=True),
                        mock.patch.object(pc.outcomes, "OUTCOMES", self.home / ".claude" / "modelscout-outcomes.jsonl")]
        for p in self.patches:
            p.start()
        pc.catalog._memo.update(key=None, data={})

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def run_hook(self, script, payload, grok=True):
        env = dict(os.environ, **self.env)
        env.pop("GROK_SESSION_ID", None)
        if grok:
            env["GROK_SESSION_ID"] = "s-1"
        return subprocess.run([sys.executable, str(HOOKS / script), "--host=claude"], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, timeout=30).stdout


class HostDetection(GrokHome):
    def test_env_wins_over_claude_flag(self):
        with mock.patch.dict(os.environ, {"GROK_SESSION_ID": "abc"}):
            self.assertEqual(pc.detect_host({}, ["--host=claude"]), "grok")
        os.environ.pop("GROK_SESSION_ID", None)
        self.assertEqual(pc.detect_host({}, ["--host=claude"]), "claude")

    def test_grok_model_provider(self):
        self.assertEqual(pc.model_provider("grok-4.7"), "xai")


class Picks(GrokHome):
    def test_stock_picks_use_plain_versions_only(self):
        picks = pc.provider_picks("grok")
        self.assertEqual(picks["T1"], "grok-4.3")
        self.assertEqual(picks["T4"], "grok-4.7")
        self.assertNotIn("grok-build-0.1", picks.values())
        self.assertNotIn("grok-4.20-0309-reasoning", picks.values())

    def test_custom_model_from_grok_config(self):
        (self.home / ".grok").mkdir()
        (self.home / ".grok" / "config.toml").write_text('[model.haiku]\nmodel = "claude-haiku-5-5"\n'
                                                         '[model.mystery]\nmodel = "not-in-catalog"\n')
        names = [m[0] for m in pc.grok_custom_models()]
        self.assertEqual(names, ["haiku"])  # picker name, and unpriced models are left out
        self.assertEqual(pc.provider_picks("grok")["T1"], "haiku")


class RulesFile(GrokHome):
    def test_setup_command_writes_rules_and_prompt_hook_is_silent(self):
        out = self.run_hook("proactive_check.py", {"hook_event_name": "UserPromptSubmit",
                                                   "prompt": "modelscout: grok setup"})
        self.assertEqual(json.loads(out)["decision"], "block")  # Grok shows `reason` to the user
        text = pc.grok_rules_path().read_text()
        self.assertTrue(text.startswith(pc.GROK_MARK))
        self.assertIn("spawn_subagent", text)
        self.assertIn("grok-4.7", text)
        # an ordinary prompt prints nothing on Grok (its context would be discarded anyway)
        self.assertEqual(self.run_hook("proactive_check.py", {"hook_event_name": "UserPromptSubmit",
                                                              "prompt": "refactor the auth module for me"}), "")

    def test_settings_change_refreshes_existing_file_only(self):
        self.assertFalse(pc.grok_refresh_if_present())
        self.assertFalse(pc.grok_rules_path().exists())
        pc.grok_write_rules()
        pc.handle_command("off", "grok")
        self.assertIn("ModelScout is off", pc.grok_rules_path().read_text())
        pc.handle_command("auto", "grok")
        self.assertIn("ModelScout is ACTIVE", pc.grok_rules_path().read_text())

    def test_remove_only_deletes_our_file(self):
        path = pc.grok_rules_path()
        path.parent.mkdir(parents=True)
        path.write_text("my own rules\n")
        self.assertIn("no Grok Build rules file", pc.handle_command("grok remove", "grok"))
        self.assertTrue(path.exists())
        self.assertFalse(pc.grok_refresh_if_present())  # never overwrites a file we did not write
        self.assertEqual(path.read_text(), "my own rules\n")
        path.unlink()
        pc.grok_write_rules()
        self.assertIn("removed", pc.handle_command("grok remove", "grok"))
        self.assertFalse(path.exists())

    def test_session_start_refreshes_only_when_present(self):
        self.run_hook("session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})
        self.assertFalse(pc.grok_rules_path().exists())
        path = pc.grok_rules_path()
        path.parent.mkdir(parents=True)
        path.write_text(pc.GROK_MARK + "\nstale\n")
        self.run_hook("session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})
        self.assertIn("ModelScout is ACTIVE", path.read_text())


class OutcomeHook(GrokHome):
    def test_spawn_subagent_payload_records_nothing(self):
        payload = {"hook_event_name": "PostToolUse", "hookEventName": "post_tool_use", "sessionId": "s-1",
                   "toolName": "spawn_subagent", "toolInput": {"description": "ModelScout: T1 · rename"},
                   "toolResult": {"subagentId": "a1"}, "tool_response": {"subagentId": "a1"}}
        self.assertEqual(self.run_hook("post_tool.py", payload), "")
        self.assertFalse((self.home / ".claude" / "modelscout-outcomes.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
