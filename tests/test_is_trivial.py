"""Regression tests for the hook's follow-up filter (issue #1).

Run: python3 -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins" / "modelscout" / "hooks"))
import proactive_check as pc  # noqa: E402

FOLLOWUPS = [
    "yes", "continue", "thanks!", "yes, test it", "ok, go on", "Yes please, do that!",
    "go ahead and run it", "no, use postgres instead", "sure thing",
    "ได้เลย ทดสอบด้วย", "โอเค ไปต่อ",
]
TASKS = [
    "ok, now refactor the auth module",
    "yes, debug the race condition in the queue",
    "sure, write a poem about cats",
    "yes, rename all the fields",
    "node script to parse logs",
    "write tests",
    "ok please build me a landing page for the bakery",
    "hello, can you add dark mode to the settings page?",
    "ไม่ทำงานเลย หน้า login ค้าง",
    "ได้เลย ช่วยเขียนเว็บไซต์ขายของออนไลน์ให้หน่อยพร้อมระบบตะกร้าสินค้า",
]


class FollowupFilter(unittest.TestCase):
    def test_followups_are_skipped(self):
        for p in FOLLOWUPS:
            with self.subTest(prompt=p):
                self.assertTrue(pc.is_trivial(p))

    def test_tasks_get_a_card(self):
        for p in TASKS:
            with self.subTest(prompt=p):
                self.assertFalse(pc.is_trivial(p))


if __name__ == "__main__":
    unittest.main()
