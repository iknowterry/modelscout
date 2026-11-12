"""SessionStart hook: the announce instruction is emitted only for startup/clear/unknown sources.
Run: python3 -m unittest discover tests -p 'test_session_start.py'
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "plugins" / "modelscout" / "hooks" / "session_start.py"
PREPEND = "prepend one line"


def big_catalog():
    return {f"p{i}": {"id": f"p{i}", "models": {f"m{i}": {"cost": {"output": i}}}} for i in range(12)}


class SessionStartTests(unittest.TestCase):
    def run_hook(self, payload):
        with tempfile.TemporaryDirectory() as home:
            cat = Path(home) / ".claude" / "model-catalog.json"
            cat.parent.mkdir(parents=True)
            cat.write_text(json.dumps(big_catalog()))
            env = {k: v for k, v in os.environ.items() if k != "HERMES_HOME"}
            env["HOME"] = home
            r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
                               text=True, env=env, timeout=30)
        self.assertEqual(r.returncode, 0)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ModelScout is ACTIVE", ctx)
        self.assertIn("Per-task behavior follows the <modelscout> block", ctx)
        return ctx

    def test_announces_for_startup_clear_and_missing(self):
        for payload in ({"source": "startup"}, {"source": "clear"}, {}):
            self.assertIn(PREPEND, self.run_hook(payload), payload)

    def test_no_announce_for_resume_and_compact(self):
        for payload in ({"source": "resume"}, {"source": "compact"}):
            self.assertNotIn(PREPEND, self.run_hook(payload), payload)


if __name__ == "__main__":
    unittest.main()
