"""Outcome recording: tier tags, Hermes subagent_stop, Claude Agent PostToolUse, `weak`.
Run: python3 -m unittest discover tests
"""
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "modelscout"
SCRIPTS = PLUGIN / "skills" / "modelscout" / "scripts"
sys.path.insert(0, str(PLUGIN / "hooks"))
import proactive_check as pc  # noqa: E402
import post_tool  # noqa: E402

MARKER = re.compile(r"^\s*(⚡\s*)?modelscout\b", re.I)  # savings.py's routed-subagent marker


def load(name, path, **kw):
    spec = importlib.util.spec_from_file_location(name, path, **kw)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "outcomes.jsonl"
        # every loaded copy of outcomes.py writes to the temp log
        self.mods = [pc.outcomes]
        self.patches = [mock.patch.object(m, "OUTCOMES", self.log) for m in self.mods]
        for p in self.patches:
            p.start()
        real = post_tool._outcomes

        def patched():
            m = real()
            m.OUTCOMES = self.log
            return m
        self.pt = mock.patch.object(post_tool, "_outcomes", patched)
        self.pt.start()

    def tearDown(self):
        self.pt.stop()
        for p in self.patches:
            p.stop()

    def rows(self):
        return pc.outcomes.read()


class Tags(unittest.TestCase):
    def test_tier_tag(self):
        o = pc.outcomes
        self.assertEqual(o.tier_from("ModelScout: T1 · rename user_id"), "T1")
        self.assertEqual(o.tier_from("⚡ modelscout: t3 · debug race"), "T3")
        self.assertIsNone(o.tier_from("ModelScout: rename user_id"))
        self.assertIsNone(o.tier_from("rename T1 things"))

    def test_tagged_goal_is_not_a_command_and_still_counts_for_savings(self):
        for g in ("ModelScout: T1 · rename user_id", "ModelScout: T2 · stay on the plan"):
            with self.subTest(goal=g):
                self.assertIsNone(pc.parse_command(g))
                self.assertTrue(MARKER.match(g))

    def test_weak_is_a_command(self):
        self.assertEqual(pc.parse_command("modelscout: weak"), "weak")


class ClaudeHook(Base):
    def payload(self, desc="ModelScout: T1 · rename user_id", status="completed", **ti):
        return {"hook_event_name": "PostToolUse", "tool_name": "Agent",
                "tool_input": {"description": desc, "prompt": "secret brief", "model": "haiku", **ti},
                "tool_response": {"status": status, "resolvedModel": "claude-haiku-4-5",
                                  "content": [{"type": "text", "text": "done"}], "totalTokens": 900}}

    def test_completed_records_ok_without_goal_text(self):
        post_tool.handle(self.payload())
        [r] = self.rows()
        self.assertEqual((r["host"], r["tier"], r["model"], r["status"]), ("claude", "T1", "claude-haiku-4-5", "ok"))
        raw = self.log.read_text()
        self.assertNotIn("rename", raw)
        self.assertNotIn("secret", raw)

    def test_skips_untagged_background_and_child_calls(self):
        post_tool.handle(self.payload(desc="Explore the repo"))
        post_tool.handle(self.payload(run_in_background=True))
        post_tool.handle(dict(self.payload(), agent_id="sub-1"))
        post_tool.handle(dict(self.payload(), tool_name="Bash"))
        self.assertEqual(self.rows(), [])

    def test_failure_and_interrupt(self):
        post_tool.handle({"hook_event_name": "PostToolUseFailure", "tool_name": "Agent",
                          "tool_input": {"description": "ModelScout: T2 · add tests", "model": "sonnet"},
                          "error": "API error", "is_interrupt": False})
        post_tool.handle({"hook_event_name": "PostToolUseFailure", "tool_name": "Agent",
                          "tool_input": {"description": "ModelScout: T2 · add tests"}, "is_interrupt": True})
        [r] = self.rows()
        self.assertEqual((r["tier"], r["model"], r["status"]), ("T2", "sonnet", "fail"))

    def test_weak_marks_latest(self):
        post_tool.handle(self.payload())
        post_tool.handle(self.payload(desc="ModelScout: T2 · write tests"))
        out = pc.handle_command("weak")
        self.assertIn("weak", out)
        a, b = self.rows()
        self.assertEqual((a["status"], b["status"]), ("ok", "fail"))
        pc.handle_command("weak")  # idempotent on the same outcome
        self.assertEqual([r["status"] for r in self.rows()], ["ok", "fail"])

    def test_concurrent_appends_stay_whole_lines(self):
        def burst():
            for _ in range(50):
                pc.outcomes.record("claude", "T1", "m" * 200, "ok")
        ts = [threading.Thread(target=burst) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        lines = self.log.read_text().splitlines()
        self.assertEqual(len(lines), 400)
        for ln in lines:
            json.loads(ln)


class HermesHook(Base):
    def setUp(self):
        super().setUp()
        hh = self.tmp / "hermes"
        hh.mkdir()
        con = sqlite3.connect(hh / "state.db")
        con.execute("create table sessions (id text primary key, model text)")
        con.execute("insert into sessions values ('child-1', 'gpt-6-luna'), ('child-2', 'gpt-6-luna')")
        con.commit()
        con.close()
        self.env = mock.patch.dict(os.environ, {"HERMES_HOME": str(hh)})
        self.env.start()
        self.plugin = load("modelscout_hermes_plugin_outcomes", PLUGIN / "__init__.py",
                           submodule_search_locations=[])
        self.plugin._core = pc  # share the patched core

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def test_routed_child_outcomes(self):
        p = self.plugin
        p._on_subagent_start(child_session_id="child-1", child_goal="ModelScout: T1 · rename user_id")
        p._on_subagent_start(child_session_id="child-2", child_goal="ModelScout: refactor auth module")
        p._on_subagent_start(child_session_id="child-3", child_goal="look something up")
        p._on_subagent_stop(child_session_id="child-1", child_status="completed")
        p._on_subagent_stop(child_session_id="child-2", child_status="failed")
        p._on_subagent_stop(child_session_id="child-3", child_status="completed")
        a, b = self.rows()
        self.assertEqual((a["host"], a["tier"], a["model"], a["status"]), ("hermes", "T1", "gpt-6-luna", "ok"))
        want = pc.guess_tier("ModelScout: refactor auth module")[0]  # untagged → guessed tier
        self.assertEqual((b["tier"], b["status"], b["why"]), (want, "fail", "failed"))
        # children still get no card
        self.assertIsNone(p._on_pre_llm_call(user_message="rename the field everywhere", session_id="child-1"))


if __name__ == "__main__":
    unittest.main()
