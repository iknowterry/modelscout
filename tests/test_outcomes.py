"""Outcome recording: tier tags, Claude Agent PostToolUse / PostToolUseFailure /
SubagentStop, Hermes subagent_stop, `weak`, weak_rate, summary.
Run: python3 -m unittest discover tests -p 'test_outcomes.py'
"""
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "modelscout"
SCRIPTS = PLUGIN / "skills" / "modelscout" / "scripts"
sys.path.insert(0, str(PLUGIN / "hooks"))
import proactive_check as pc  # noqa: E402
import post_tool  # noqa: E402

MARKER = re.compile(r"^\s*(⚡\s*)?modelscout\b", re.I)  # savings.py's routed-subagent marker
GOAL = "ModelScout: T1 · rename user_id"
PROMPT = "secret brief about the payroll table"


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
        self.patches = [mock.patch.object(pc.outcomes, "OUTCOMES", self.log)]
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

    def statuses(self):
        return [r["status"] for r in self.rows()]

    # synthetic payloads shaped like the real ones
    def launch(self, aid="a0a19756f1b0d4616", desc=GOAL, resolved="claude-haiku-4-5", **ti):
        tr = {"isAsync": True, "status": "async_launched", "agentId": aid, "description": desc,
              "prompt": PROMPT, "outputFile": f"/tmp/tasks/{aid}.output"}
        if resolved:
            tr["resolvedModel"] = resolved
        return post_tool.handle({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                                 "tool_input": {"description": desc, "prompt": PROMPT, **ti},
                                 "tool_response": tr})

    def stop(self, aid="a0a19756f1b0d4616", transcript=None, last="All renamed."):
        return post_tool.handle({"hook_event_name": "SubagentStop", "session_id": "s1",
                                 "transcript_path": "/tmp/s1.jsonl", "cwd": "/tmp",
                                 "agent_id": aid, "agent_type": "general-purpose",
                                 "agent_transcript_path": str(transcript or self.tmp / "missing.jsonl"),
                                 "last_assistant_message": last, "stop_hook_active": False})

    def foreground(self, desc=GOAL, aid="af00000000000001", model="haiku", **tr):
        resp = {"status": "completed", "agentId": aid, "agentType": "general-purpose",
                "content": [{"type": "text", "text": "done: renamed 12 files"}], "totalDurationMs": 4000,
                "totalTokens": 900, "usage": {"input_tokens": 10}, "resolvedModel": "claude-haiku-4-5", **tr}
        return post_tool.handle({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                                 "tool_input": {"description": desc, "prompt": PROMPT, "model": model},
                                 "tool_response": resp})

    def failure(self, error, interrupt=False, desc="ModelScout: T2 · add tests"):
        return post_tool.handle({"hook_event_name": "PostToolUseFailure", "tool_name": "Agent",
                                 "tool_input": {"description": desc, "prompt": PROMPT, "model": "sonnet"},
                                 "error": error, "is_interrupt": interrupt})

    def transcript(self, name, records):
        p = self.tmp / name
        p.write_text("".join(json.dumps(r) + "\n" for r in records))
        return p


def asst(model, text="ok", **extra):
    return {"type": "assistant", "isSidechain": True, "agentId": "x",
            "message": {"model": model, "content": [{"type": "text", "text": text}]}, **extra}


class Tags(unittest.TestCase):
    def test_tier_tag(self):
        o = pc.outcomes
        self.assertEqual(o.tier_from(GOAL), "T1")
        self.assertEqual(o.tier_from("⚡ modelscout: t3 · debug race"), "T3")
        self.assertIsNone(o.tier_from("ModelScout: rename user_id"))
        self.assertIsNone(o.tier_from("rename T1 things"))

    def test_tagged_goal_is_not_a_command_and_still_counts_for_savings(self):
        for g in (GOAL, "ModelScout: T2 · stay on the plan"):
            with self.subTest(goal=g):
                self.assertIsNone(pc.parse_command(g))
                self.assertTrue(MARKER.match(g))

    def test_weak_is_a_command(self):
        self.assertEqual(pc.parse_command("modelscout: weak"), "weak")


class ClaudeAsync(Base):
    def test_launch_pending_then_stop_ok(self):
        for bg in (True, None):  # async even without run_in_background
            with self.subTest(run_in_background=bg):
                aid = f"a{bg}"
                self.launch(aid=aid, **({"run_in_background": True} if bg else {}))
                r = pc.outcomes.find(aid)
                self.assertEqual((r["status"], r["tier"], r["model"]), ("pending", "T1", "claude-haiku-4-5"))
                self.stop(aid=aid)
                r = pc.outcomes.find(aid)
                self.assertEqual((r["status"], r["model"], r["host"]), ("ok", "claude-haiku-4-5", "claude"))
                self.assertIsNotNone(r["done"])

    def test_stop_for_unknown_agent_records_nothing(self):
        self.stop(aid="anotours")
        self.assertFalse(self.log.exists())
        self.launch(aid="a1")
        self.stop(aid="a2")
        self.assertEqual(self.statuses(), ["pending"])

    def test_double_stop_is_noop(self):
        self.launch(aid="a1")
        self.stop(aid="a1")
        n = len(self.log.read_text().splitlines())
        self.stop(aid="a1")
        self.assertEqual(len(self.log.read_text().splitlines()), n)
        self.assertEqual(self.statuses(), ["ok"])

    def test_model_filled_from_transcript(self):
        t = self.transcript("agent-a1.jsonl", [asst("claude-sonnet-5-5"), {"type": "user", "message": {}},
                                                asst("claude-sonnet-5-5", "final")])
        self.launch(aid="a1", resolved=None)  # no resolvedModel, no tool_input.model
        self.assertIsNone(pc.outcomes.find("a1")["model"])
        self.stop(aid="a1", transcript=t)
        self.assertEqual(pc.outcomes.find("a1")["model"], "claude-sonnet-5-5")
        # an alias from tool_input.model is upgraded to the concrete id
        self.launch(aid="a2", resolved=None, model="sonnet")
        self.stop(aid="a2", transcript=t)
        self.assertEqual(pc.outcomes.find("a2")["model"], "claude-sonnet-5-5")
        # a concrete launch model is kept
        self.launch(aid="a3", resolved="claude-haiku-4-5")
        self.stop(aid="a3", transcript=t)
        self.assertEqual(pc.outcomes.find("a3")["model"], "claude-haiku-4-5")

    def test_async_api_error_tail_is_error_not_ok(self):
        t = self.transcript("agent-a1.jsonl", [
            asst("claude-sonnet-5-5", "working"),
            asst("<synthetic>", "You've hit your session limit · resets 2:10am",
                 isApiErrorMessage=True, error="rate_limit", apiErrorStatus=429)])
        self.launch(aid="a1", resolved=None)
        self.stop(aid="a1", transcript=t, last="You've hit your session limit · resets 2:10am")
        r = pc.outcomes.find("a1")
        self.assertEqual((r["status"], r["why"], r["model"]), ("error", "limit", "claude-sonnet-5-5"))
        self.assertNotIn("<synthetic>", self.log.read_text())
        t2 = self.transcript("agent-a2.jsonl", [asst("<synthetic>", "API Error: Connection closed mid-response",
                                                     isApiErrorMessage=True, error="server_error")])
        self.launch(aid="a2", resolved=None)
        self.stop(aid="a2", transcript=t2)
        r = pc.outcomes.find("a2")
        self.assertEqual((r["status"], r["why"], r["model"]), ("error", "unavailable", None))

    def test_large_transcript_reads_tail_only(self):
        big = [asst("claude-opus-5", "x" * 500) for _ in range(300)] + [asst("claude-sonnet-5-5")]
        t = self.transcript("agent-big.jsonl", big)
        self.assertGreater(t.stat().st_size, post_tool.TAIL)
        self.assertEqual(post_tool.transcript_tail(t), ("claude-sonnet-5-5", None))
        self.assertEqual(post_tool.transcript_tail(self.tmp / "nope.jsonl"), (None, None))


class ClaudeForeground(Base):
    def test_completed_records_ok(self):
        self.foreground()
        [r] = self.rows()
        self.assertEqual((r["host"], r["tier"], r["model"], r["status"], r["id"]),
                         ("claude", "T1", "claude-haiku-4-5", "ok", "af00000000000001"))
        # SubagentStop for a foreground agent finds nothing pending; a repeat PostToolUse is ignored
        self.stop(aid="af00000000000001")
        self.foreground()
        self.assertEqual(self.statuses(), ["ok"])

    def test_failures_are_errors_never_weak(self):
        cases = [("claude-sonnet-5 is temporarily unavailable, please try again", False, "unavailable"),
                 ("Agent terminated early due to an API error: You've hit your usage limit", False, "limit"),
                 ("Permission for this action was denied by the user", False, "denied"),
                 ("[Request interrupted by user for tool use]", False, "interrupt"),
                 ("", True, "interrupt"),
                 ("something odd", False, "other")]
        for err, intr, _ in cases:
            self.failure(err, interrupt=intr)
        rows = self.rows()
        self.assertEqual([r["status"] for r in rows], ["error"] * len(cases))
        self.assertEqual([r["why"] for r in rows], [c[2] for c in cases])
        self.assertEqual({(r["tier"], r["model"]) for r in rows}, {("T2", "sonnet")})
        self.assertIsNone(pc.outcomes.mark_last_weak())  # nothing finished to mark
        self.assertEqual(pc.outcomes.weak_rate("T2"), (0, 0))

    def test_skips_untagged_and_child_calls(self):
        self.foreground(desc="Explore the repo")
        self.launch(desc="Explore the repo")
        self.failure("API error", desc="Explore the repo")
        post_tool.handle(dict(hook_event_name="PostToolUse", tool_name="Agent", agent_id="sub-1",
                              tool_input={"description": GOAL}, tool_response={"status": "completed"}))
        post_tool.handle({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                          "tool_input": {"description": GOAL}, "tool_response": {"status": "completed"}})
        post_tool.handle(None)
        post_tool.handle({"hook_event_name": "SubagentStop"})
        self.assertEqual(self.rows(), [])

    def test_privacy(self):
        t = self.transcript("agent-a1.jsonl", [asst("claude-sonnet-5-5", "the payroll secret")])
        self.launch(aid="a1", resolved=None)
        self.stop(aid="a1", transcript=t, last="the payroll secret")
        self.foreground()
        self.failure("API error: You've hit your usage limit for claude-sonnet-5")
        pc.outcomes.mark_last_weak()
        raw = self.log.read_text()
        for word in ("rename", "secret", "payroll", "usage limit", "API error", "agent-a1", str(self.tmp),
                     "done: renamed", "add tests"):
            self.assertNotIn(word, raw)
        allowed = {"id", "ts", "host", "tier", "model", "status", "why", "ref"}
        for ln in raw.splitlines():
            self.assertLessEqual(set(json.loads(ln)), allowed)


class Weak(Base):
    def test_weak_marks_latest_finished_and_is_idempotent(self):
        self.foreground(aid="f1")
        self.foreground(desc="ModelScout: T2 · write tests", aid="f2")
        out = pc.handle_command("weak")
        self.assertIn("weak", out)
        self.assertEqual(self.statuses(), ["ok", "weak"])
        n = len(self.log.read_text().splitlines())
        pc.handle_command("weak")  # same outcome again: nothing written
        self.assertEqual(self.statuses(), ["ok", "weak"])
        self.assertEqual(len(self.log.read_text().splitlines()), n)

    def test_weak_skips_error_and_pending(self):
        self.foreground(aid="f1")
        self.launch(aid="a1")              # still pending
        self.failure("usage limit")        # error
        r = pc.outcomes.mark_last_weak()
        self.assertEqual(r["id"], "f1")
        self.assertEqual(r["tier"], "T1")
        self.assertEqual(self.statuses(), ["weak", "pending", "error"])

    def test_weak_follows_finish_order_not_launch_order(self):
        self.launch(aid="a1")
        self.launch(aid="a2", desc="ModelScout: T3 · debug race")
        self.stop(aid="a2")
        with mock.patch.object(time, "time", return_value=time.time() + 60):
            self.stop(aid="a1")  # a1 launched first but finished last
        self.assertEqual(pc.outcomes.mark_last_weak()["id"], "a1")
        self.assertEqual(pc.outcomes.find("a2")["status"], "ok")

    def test_none_when_empty(self):
        self.assertIsNone(pc.outcomes.mark_last_weak())
        self.assertIn("no routed subagent", pc.handle_command("weak"))

    def test_weak_rate_ignores_errors_and_pending(self):
        for i in range(3):
            self.foreground(aid=f"f{i}")
        pc.outcomes.mark_last_weak()
        for _ in range(4):
            self.failure("temporarily unavailable", desc=GOAL)
        self.launch(aid="a1")
        o = pc.outcomes
        self.assertEqual(o.weak_rate("T1"), (3, 1))
        self.assertEqual(o.weak_rate("T1", "claude-haiku-4-5"), (3, 1))
        self.assertEqual(o.weak_rate("T1", "sonnet"), (0, 0))  # the errors' model: errors never count
        self.assertEqual(o.weak_rate("T1", last=1), (1, 1))
        self.assertEqual(o.weak_rate("T4"), (0, 0))

    def test_summary(self):
        self.assertIn("none recorded", pc.outcomes.summary())
        self.foreground(aid="f1")
        self.foreground(aid="f2")
        pc.outcomes.mark_last_weak()
        self.failure("usage limit", desc=GOAL)
        self.launch(aid="a1")
        pc.outcomes._append({"id": "old", "ts": round(time.time()) - 3 * 86400, "host": "claude",
                             "tier": "T1", "model": "claude-haiku-4-5", "status": "pending"})
        s = pc.handle_command("outcomes")
        self.assertIn("T1 claude-haiku-4-5: 2 finished, 1 weak, 0 errors", s)
        self.assertIn("T1 sonnet: 0 finished, 0 weak, 1 errors", s)
        self.assertIn("(1 still running)", s)
        self.assertIn("Only weak results count against a model", s)

    def test_legacy_lines_read(self):
        self.log.write_text("\n".join([
            json.dumps({"id": "o1", "ts": 1, "host": "claude", "tier": "T1", "model": "m", "status": "ok", "why": "completed"}),
            json.dumps({"id": "o2", "ts": 2, "host": "hermes", "tier": "T2", "model": "m", "status": "fail", "why": "failed"}),
            json.dumps({"ts": 3, "ref": "o1", "verdict": "fail", "why": "weak"}),
            json.dumps({"ts": 4, "ref": "nobody", "verdict": "fail"}),
            "not json", "[1, 2]", ""]) + "\n")
        a, b = self.rows()
        self.assertEqual((a["status"], b["status"], b["why"]), ("weak", "error", "failed"))
        self.assertEqual(pc.outcomes.weak_rate("T2"), (0, 0))
        self.assertIn("T1 m: 1 finished, 1 weak, 0 errors", pc.outcomes.summary())

    def test_concurrent_appends_stay_whole_lines(self):
        def burst():
            for _ in range(50):
                pc.outcomes.record("claude", "T1", "m" * 70, "ok")
        ts = [threading.Thread(target=burst) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        lines = self.log.read_text().splitlines()
        self.assertEqual(len(lines), 400)
        for ln in lines:
            json.loads(ln)
        self.assertEqual(len(self.rows()), 400)


class HermesHook(Base):
    def setUp(self):
        super().setUp()
        hh = self.tmp / "hermes"
        hh.mkdir()
        con = sqlite3.connect(hh / "state.db")
        con.execute("create table sessions (id text primary key, model text)")
        con.executemany("insert into sessions values (?, 'gpt-6-luna')", [(f"child-{i}",) for i in range(1, 6)])
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
        p._on_subagent_start(child_session_id="child-1", child_goal=GOAL)
        p._on_subagent_start(child_session_id="child-2", child_goal="ModelScout: refactor auth module")
        p._on_subagent_start(child_session_id="child-3", child_goal="ModelScout: T2 · write docs")
        p._on_subagent_start(child_session_id="child-4", child_goal="ModelScout: T2 · write more docs")
        p._on_subagent_start(child_session_id="child-9", child_goal="look something up")
        p._on_subagent_stop(child_session_id="child-1", child_status="completed")
        p._on_subagent_stop(child_session_id="child-2", child_status="failed")
        p._on_subagent_stop(child_session_id="child-3", child_status="interrupted")
        p._on_subagent_stop(child_session_id="child-4", child_status="error")
        p._on_subagent_stop(child_session_id="child-9", child_status="completed")
        p._on_subagent_stop(child_session_id="never-started", child_status="completed")
        a, b, c, d = self.rows()
        self.assertEqual((a["host"], a["tier"], a["model"], a["status"]), ("hermes", "T1", "gpt-6-luna", "ok"))
        want = pc.guess_tier("ModelScout: refactor auth module")[0]  # untagged → guessed tier
        self.assertEqual((b["tier"], b["status"], b["why"]), (want, "error", "failed"))
        self.assertEqual((c["status"], c["why"]), ("error", "interrupted"))
        self.assertEqual((d["status"], d["why"]), ("error", "error"))
        self.assertEqual(pc.outcomes.mark_last_weak()["model"], "gpt-6-luna")  # only the ok one
        self.assertNotIn("docs", self.log.read_text())
        # children still get no card
        self.assertIsNone(p._on_pre_llm_call(user_message="rename the field everywhere", session_id="child-1"))


class HookScript(Base):
    def test_shim_prints_nothing_and_exits_zero(self):
        import subprocess
        sh = PLUGIN / "hooks" / "post-tool.sh"
        for payload in ("not json", json.dumps({"hook_event_name": "SubagentStop", "agent_id": "zz"})):
            r = subprocess.run(["bash", str(sh)], input=payload, capture_output=True, text=True,
                               env={**os.environ, "HOME": str(self.tmp)}, timeout=30)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
