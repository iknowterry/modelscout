"""Benchmark harness: run.py end to end with a fake `claude`, and report.py math.
No tokens are spent. Run: python3 -m unittest discover tests
"""
import importlib.util
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FAKE_CLAUDE = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys, uuid
    from pathlib import Path
    argv = sys.argv[1:]
    routed = "--plugin-dir" in argv
    sid = str(uuid.uuid4())
    Path("feature.py").write_text("def answer():\\n    return 42\\n")
    proj = Path(os.environ["FAKE_PROJECTS"]) / "-tmp-modelscout-bench-x"
    proj.mkdir(parents=True, exist_ok=True)
    def asst(mid, model, out, content=None):
        return json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "content": content or [],
               "usage": {"input_tokens": 1000, "output_tokens": out, "cache_creation_input_tokens": 0,
                         "cache_read_input_tokens": 0}}})
    lines = []
    if routed:
        lines.append(json.dumps({"type": "attachment", "attachment": {"type": "hook_additional_context",
                     "hookEvent": "UserPromptSubmit", "content": ["<modelscout host=\\"claude\\" mode=\\"auto\\">"]}}))
        lines.append(asst("m1", "claude-opus-5-5", 200, [{"type": "tool_use", "name": "Agent", "id": "tu1",
                     "input": {"description": "ModelScout: T1 · add answer", "model": "haiku"}}]))
        sub = proj / sid / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-a1.jsonl").write_text(asst("s1", "claude-haiku-5-5", 4000) + "\\n")
        state = Path(os.environ["MODELSCOUT_STATE_DIR"])
        (state / "modelscout-outcomes.jsonl").write_text(json.dumps({"id": "a1", "status": "ok", "tier": "T1"}) + "\\n")
    else:
        lines.append(asst("m1", "claude-opus-5-5", 4200))
        lines.append(asst("m1", "claude-opus-5-5", 4200))  # duplicate message id: counted once
        lines.append(asst("m2", "claude-opus-5-5", 0, [{"type": "text", "text": "mentions <modelscout host= in passing"}]))
    (proj / f"{sid}.jsonl").write_text("\\n".join(lines) + "\\n")
    print(json.dumps({"session_id": sid, "total_cost_usd": 0.1, "is_error": False, "num_turns": 2}))
''')


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (bindir / "claude").write_text(FAKE_CLAUDE)
        (bindir / "claude").chmod(0o755)
        fixture = self.tmp / "fixture"
        (fixture / "tests").mkdir(parents=True)
        (fixture / "tests" / "__init__.py").write_text("")
        (fixture / "tests" / "test_ok.py").write_text("import unittest\nclass T(unittest.TestCase):\n"
                                                      "    def test_ok(self):\n        pass\n")
        task = self.tmp / "tasks" / "t1-demo"
        (task / "check").mkdir(parents=True)
        (task / "task.json").write_text(json.dumps({"id": "t1-demo", "tier": "T1", "title": "demo",
                                                    "prompt": "Add answer() returning 42 in feature.py",
                                                    "timeout_min": 1}))
        (task / "check" / "__init__.py").write_text("")
        (task / "check" / "test_feature.py").write_text(
            "import unittest\nfrom feature import answer\nclass T(unittest.TestCase):\n"
            "    def test_answer(self):\n        self.assertEqual(answer(), 42)\n")
        self.run_mod = _mod("bench_run_test", BENCH / "run.py")
        self.run_mod.FIXTURE = fixture
        self.run_mod.TASKS = self.tmp / "tasks"
        self.run_mod.PROJECTS = self.tmp / "projects"
        self.env = mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
                                                "FAKE_PROJECTS": str(self.tmp / "projects")})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_plan_only_spends_nothing(self):
        with mock.patch.object(self.run_mod, "one_run", side_effect=AssertionError("ran")):
            self.assertEqual(self.run_mod.main([]), 0)

    def test_both_arms_measured_checked_and_validated(self):
        task = self.run_mod.load_tasks()[0]
        out = self.tmp / "out"
        out.mkdir()
        prices = self.run_mod._prices()
        base = self.run_mod.one_run(task, "baseline", "opus", 1, out, prices, keep=False)
        rout = self.run_mod.one_run(task, "routed", "opus", 1, out, prices, keep=False)
        for r in (base, rout):
            self.assertTrue(r["passed"], r["checks"])
            self.assertTrue(r["valid"], r["problems"])
        self.assertEqual(base["usage"]["per_model"]["claude-opus-5-5"]["requests"], 2)  # m1 deduplicated, plus m2
        self.assertEqual(set(rout["usage"]["per_model"]), {"claude-opus-5-5", "claude-haiku-5-5"})
        self.assertEqual(rout["usage"]["subagent_files"], 1)
        self.assertEqual(rout["outcomes"][0]["status"], "ok")
        self.assertLess(rout["usage"]["cost"], base["usage"]["cost"])

        rep = _mod("bench_report_test", BENCH / "report.py")
        meta, recs = rep.load(out)
        s = rep.summarize(recs)
        self.assertEqual(s["total"]["tasks"], 1)
        self.assertGreater(s["total"]["saved"], 0)
        self.assertIn("less", rep.markdown(meta, s))

    def test_routed_run_without_block_is_invalid(self):
        task = self.run_mod.load_tasks()[0]
        out = self.tmp / "out2"
        out.mkdir()
        with mock.patch.object(self.run_mod, "claude_cmd",
                               lambda t, arm, m: ["claude", "-p", t["prompt"]]):  # plugin never loaded
            r = self.run_mod.one_run(task, "routed", "opus", 1, out, self.run_mod._prices(), keep=False)
        self.assertFalse(r["valid"])
        rep = _mod("bench_report_test2", BENCH / "report.py")
        s = rep.summarize(rep.load(out)[1])
        self.assertIsNone(s["total"])
        self.assertTrue(s["invalid"])


class StateDir(unittest.TestCase):
    def test_state_dir_redirects_settings_and_outcomes(self):
        d = tempfile.mkdtemp()
        scripts = REPO / "plugins" / "modelscout" / "skills" / "modelscout" / "scripts"
        with mock.patch.dict(os.environ, {"MODELSCOUT_STATE_DIR": d}):
            p = _mod("prefs_state_test", scripts / "prefs.py")
            o = _mod("outcomes_state_test", scripts / "outcomes.py")
        self.assertEqual(p.PROFILE, Path(d) / "modelscout-profile.json")
        self.assertEqual(o.OUTCOMES, Path(d) / "modelscout-outcomes.jsonl")


if __name__ == "__main__":
    unittest.main()
