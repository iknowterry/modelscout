import contextlib
import io
import os
import pathlib
import tempfile
import unittest

from shoplib import cli

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV = "sku,name,price,quantity\nZ9,Zip Tie,1.00,0\nA1,Apple Pie,8.50,3\nM5,Mug,5.00,5\nB2,Blue Mug,5.00,4\nQ7,Quilt,50.00,12\n"


def run(path, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(["--catalog", path, *argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class LowStockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "catalog.csv")
        with open(self.path, "w") as f:
            f.write(CSV)

    def test_default_threshold_is_five_and_strict(self):
        code, out, _ = run(self.path, "low-stock")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["A1: 3", "B2: 4", "Z9: 0"])

    def test_custom_threshold(self):
        code, out, _ = run(self.path, "low-stock", "--threshold", "13")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["A1: 3", "B2: 4", "M5: 5", "Q7: 12", "Z9: 0"])

    def test_threshold_one(self):
        self.assertEqual(run(self.path, "low-stock", "--threshold", "1")[1].splitlines(), ["Z9: 0"])

    def test_nothing_low(self):
        code, out, _ = run(self.path, "low-stock", "--threshold", "0")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "No low-stock products.")

    def test_missing_catalog_is_empty(self):
        code, out, _ = run(os.path.join(os.path.dirname(self.path), "none.csv"), "low-stock")
        self.assertEqual((code, out.strip()), (0, "No low-stock products."))

    def test_other_commands_still_work(self):
        self.assertEqual(run(self.path, "value")[0], 0)
        self.assertIn("A1\tApple Pie\t3\t$8.50", run(self.path, "list")[1])

    def test_test_was_added(self):
        self.assertIn("low-stock", (ROOT / "tests" / "test_cli.py").read_text())


if __name__ == "__main__":
    unittest.main()
