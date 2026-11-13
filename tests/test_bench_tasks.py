"""Guards the benchmark task set: every task must be solvable and not already solved."""
import subprocess
import sys
import unittest
from pathlib import Path

VALIDATOR = Path(__file__).resolve().parents[1] / "bench" / "validate_tasks.py"


class BenchTaskSetTests(unittest.TestCase):
    def test_validate_tasks_passes(self):
        proc = subprocess.run([sys.executable, str(VALIDATOR)], capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
