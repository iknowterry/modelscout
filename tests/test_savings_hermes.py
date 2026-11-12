"""Hermes savings: children titled "Subagent: ModelScout: …" are counted.
Run: python3 -m unittest discover tests
"""
import importlib.util
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "plugins/modelscout/skills/modelscout/scripts/savings.py"
spec = importlib.util.spec_from_file_location("ms_savings", SCRIPT)
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)


def make_db(path, child_title, goal):
    con = sqlite3.connect(path)
    con.executescript("""
      CREATE TABLE sessions (id TEXT, model TEXT, parent_session_id TEXT, started_at REAL,
        ended_at REAL, title TEXT, input_tokens INT, output_tokens INT,
        cache_read_tokens INT, cache_write_tokens INT);
      CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT);
      CREATE TABLE session_model_usage (session_id TEXT, model TEXT, input_tokens INT,
        output_tokens INT, cache_read_tokens INT, cache_write_tokens INT);
    """)
    now = time.time()
    con.execute("INSERT INTO sessions VALUES ('p','gpt-6-sol',NULL,?,?,'parent',0,0,0,0)", (now - 60, now))
    con.execute("INSERT INTO sessions VALUES ('c','gpt-6-luna','p',?,?,?,0,0,0,0)", (now - 50, now - 10, child_title))
    con.execute("INSERT INTO messages VALUES ('c','user',?)", (goal,))
    con.execute("INSERT INTO session_model_usage VALUES ('c','gpt-6-luna',23821,1288,61184,0)")
    con.commit()
    con.close()


class HermesSavings(unittest.TestCase):
    def scan(self, title, goal):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "state.db"
            make_db(db, title, goal)
            return sv.scan_hermes(1, False, db=db)

    def test_subagent_prefixed_title_is_counted(self):
        routes = self.scan("Subagent: ModelScout: Rename user_id…", "ModelScout: Rename user_id to account_id")
        self.assertEqual(len(routes), 1)
        self.assertEqual((routes[0]["main"], routes[0]["routed"]), ("gpt-6-sol", "gpt-6-luna"))
        self.assertEqual(routes[0]["usage"]["cache_read"], 61184)

    def test_untagged_child_is_skipped(self):
        self.assertEqual(self.scan("Subagent: Rename user_id", "Rename user_id to account_id"), [])


if __name__ == "__main__":
    unittest.main()
