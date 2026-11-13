import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / "tests" / "test_report.py"

# (old, new) edits applied to shoplib/report.py. A good test file fails on most of them.
MUTANTS = [
    ('if order.status == "cancelled":', 'if False:'),
    ('key=lambda item: (-item[1], item[0])', 'key=lambda item: (item[1], item[0])'),
    ('ranked[:top_n]', 'ranked[:top_n + 1]'),
    ('revenue += service.total_cents(order)', 'revenue += order.subtotal_cents'),
    ('product.quantity < threshold', 'product.quantity <= threshold'),
    ('units_by_sku[line.sku] += line.qty', 'units_by_sku[line.sku] += 1'),
    ('enumerate(summary.top_skus, start=1)', 'enumerate(summary.top_skus, start=0)'),
    ('f"Total value: {', 'f"Total: {'),
    ('count += 1', 'count += 2'),
]
KILL_AT_LEAST = 7


def run_tests(root):
    proc = subprocess.run([sys.executable, "-m", "unittest", "tests.test_report"], cwd=root,
                          capture_output=True, text=True, timeout=120,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": ""})
    return proc.returncode, proc.stdout + proc.stderr


class ReportTestsQuality(unittest.TestCase):
    def test_file_exists_and_imports_report(self):
        self.assertTrue(TEST_FILE.is_file(), "tests/test_report.py is missing")
        self.assertIn("report", TEST_FILE.read_text())

    def test_passes_on_current_code_with_enough_tests(self):
        code, out = run_tests(ROOT)
        self.assertEqual(code, 0, out)
        match = re.search(r"Ran (\d+) tests?", out)
        self.assertIsNotNone(match, out)
        self.assertGreaterEqual(int(match.group(1)), 8)

    def test_catches_regressions(self):
        survivors = []
        for old, new in MUTANTS:
            with tempfile.TemporaryDirectory() as tmp:
                project = pathlib.Path(tmp) / "p"
                shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns("_bench_check", "__pycache__", ".git"))
                report = project / "shoplib" / "report.py"
                source = report.read_text()
                self.assertIn(old, source, f"mutant target missing: {old!r}")
                report.write_text(source.replace(old, new, 1))
                code, _ = run_tests(project)
                if code == 0:
                    survivors.append(old)
        killed = len(MUTANTS) - len(survivors)
        self.assertGreaterEqual(killed, KILL_AT_LEAST,
                                f"tests caught {killed}/{len(MUTANTS)} injected bugs; missed: {survivors}")


if __name__ == "__main__":
    unittest.main()
