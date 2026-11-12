"""Model catalog: merged loading, staleness, refresh, and the refresh command.
Run: python3 -m unittest discover tests
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "modelscout"
SCRIPTS = PLUGIN / "skills" / "modelscout" / "scripts"
sys.path.insert(0, str(PLUGIN / "hooks"))
import proactive_check as pc  # noqa: E402


def fresh_catalog_module():
    spec = importlib.util.spec_from_file_location("modelscout_catalog_test", SCRIPTS / "catalog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, data, age_days=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    t = time.time() - age_days * 86400
    os.utime(path, (t, t))


def big_catalog():
    return {f"p{i}": {"id": f"p{i}", "models": {f"m{i}": {"cost": {"output": i}}}} for i in range(12)}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cat = fresh_catalog_module()
        self.cat.CLAUDE_CATALOG = self.tmp / ".claude" / "model-catalog.json"
        self.cat.ATTEMPT_STAMP = self.tmp / ".claude" / "modelscout-catalog-attempt"
        self.env = mock.patch.dict(os.environ, {"HERMES_HOME": str(self.tmp / ".hermes")})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_merge_newest_file_wins_per_model(self):
        write(self.cat.CLAUDE_CATALOG, {"openai": {"name": "OpenAI", "models": {
            "a": {"cost": {"output": 1}}, "old-only": {"cost": {"output": 2}}}}}, age_days=3)
        write(self.cat.hermes_cache(), {"openai": {"name": "OpenAI", "models": {
            "a": {"cost": {"output": 9}}, "new-only": {"cost": {"output": 3}}}},
            "anthropic": {"models": {"c": {}}}}, age_days=0)
        m = self.cat.load()
        self.assertEqual(m["openai"]["models"]["a"]["cost"]["output"], 9)
        self.assertIn("old-only", m["openai"]["models"])
        self.assertIn("new-only", m["openai"]["models"])
        self.assertIn("anthropic", m)

    def test_stale_and_retry_stamp(self):
        self.assertTrue(self.cat.needs_refresh())  # no catalog at all
        write(self.cat.CLAUDE_CATALOG, big_catalog(), age_days=10)
        self.assertTrue(self.cat.needs_refresh())
        self.cat.ATTEMPT_STAMP.touch()
        self.assertFalse(self.cat.needs_refresh())  # tried recently: don't hammer
        write(self.cat.CLAUDE_CATALOG, big_catalog(), age_days=1)
        self.cat.ATTEMPT_STAMP.unlink()
        self.assertFalse(self.cat.needs_refresh())

    def test_fresh_hermes_cache_counts(self):
        write(self.cat.hermes_cache(), big_catalog(), age_days=0)
        self.assertFalse(self.cat.is_stale())

    def test_refresh_writes_valid_catalog(self):
        with mock.patch.object(self.cat, "_fetch", return_value=json.dumps(big_catalog()).encode()):
            ok, msg = self.cat.refresh()
        self.assertTrue(ok, msg)
        self.assertEqual(len(json.loads(self.cat.CLAUDE_CATALOG.read_text())), 12)

    def test_refresh_keeps_old_catalog_on_bad_or_failed_fetch(self):
        write(self.cat.CLAUDE_CATALOG, big_catalog(), age_days=10)
        before = self.cat.CLAUDE_CATALOG.read_text()
        for fetch in (mock.Mock(return_value=b'{"only": {}}'), mock.Mock(return_value=b"<html>"),
                      mock.Mock(side_effect=OSError("offline"))):
            with self.subTest(fetch=fetch), mock.patch.object(self.cat, "_fetch", fetch):
                ok, _ = self.cat.refresh()
                self.assertFalse(ok)
                self.assertEqual(self.cat.CLAUDE_CATALOG.read_text(), before)


class RefreshCommand(unittest.TestCase):
    def test_refresh_is_a_command(self):
        for p in ("modelscout: refresh", "ModelScout: update catalog", "modelscout: catalog off"):
            with self.subTest(prompt=p):
                self.assertIsNotNone(pc.parse_command(p))
        self.assertIsNone(pc.parse_command("ModelScout: refresh the dashboard data every hour"))

    def test_hermes_refresh_makes_no_network_call(self):
        with mock.patch.object(pc.catalog, "refresh", side_effect=AssertionError("network")):
            out = pc.handle_command("refresh", "hermes")
        self.assertIn("Hermes keeps the model catalog fresh", out)

    def test_other_hosts_refresh_now(self):
        with mock.patch.object(pc.catalog, "refresh", return_value=(True, "catalog refreshed: 1 providers, 1 models")) as r:
            out = pc.handle_command("refresh", "claude")
        r.assert_called_once()
        self.assertIn("catalog refreshed", out)


class SessionStart(unittest.TestCase):
    def test_stdout_is_json_and_no_fetch_when_fresh(self):
        home = Path(tempfile.mkdtemp())
        write(home / ".claude" / "model-catalog.json", big_catalog(), age_days=0)
        env = dict(os.environ, HOME=str(home), HERMES_HOME=str(home / ".hermes"))
        out = subprocess.run([sys.executable, str(PLUGIN / "hooks" / "session_start.py")],
                             input="{}", capture_output=True, text=True, env=env, timeout=30).stdout
        json.loads(out)
        self.assertFalse((home / ".claude" / "modelscout-catalog-attempt").exists())

    def test_auto_refresh_off_skips_fetch(self):
        home = Path(tempfile.mkdtemp())
        write(home / ".claude" / "modelscout-profile.json", {"catalog_auto_refresh": False})
        env = dict(os.environ, HOME=str(home), HERMES_HOME=str(home / ".hermes"))
        out = subprocess.run([sys.executable, str(PLUGIN / "hooks" / "session_start.py")],
                             input="{}", capture_output=True, text=True, env=env, timeout=30).stdout
        json.loads(out)
        self.assertFalse((home / ".claude" / "modelscout-catalog-attempt").exists())


if __name__ == "__main__":
    unittest.main()
