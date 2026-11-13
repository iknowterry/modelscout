import ast
import contextlib
import io
import os
import pathlib
import tempfile
import unittest

from shoplib import cli, csvio
from shoplib.errors import ValidationError

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(path, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(["--catalog", path, *argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def names_used(path):
    tree = ast.parse(path.read_text())
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imported.add((n.module or "").split(".")[0])
    return used, imported


class ParseCentsTests(unittest.TestCase):
    def test_valid_inputs(self):
        from shoplib.money import parse_cents
        cases = {"12.34": 1234, "12": 1200, "0": 0, "0.05": 5, "$1,234.50": 123450, " 7.5 ": 750,
                 "$0.99": 99, "1,000": 100000, "19.990": 1999, "100.00": 10000}
        for text, cents in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_cents(text), cents)
                self.assertIsInstance(parse_cents(text), int)

    def test_invalid_inputs(self):
        from shoplib.money import parse_cents
        for text in ["abc", "", "-1", "-0.01", "1.005", "0.001", "NaN", "Infinity", "1.2.3", "$"]:
            with self.subTest(text=text):
                with self.assertRaises(ValidationError) as ctx:
                    parse_cents(text)
                self.assertEqual(str(ctx.exception), f"invalid price: {text!r}")


class DuplicationRemovedTests(unittest.TestCase):
    def test_csvio_and_cli_use_parse_cents_and_have_no_decimal_logic(self):
        for name in ("csvio.py", "cli.py"):
            used, imported = names_used(ROOT / "shoplib" / name)
            self.assertIn("parse_cents", used, f"{name} does not call parse_cents")
            self.assertNotIn("decimal", imported, f"{name} still imports decimal")
            self.assertNotIn("Decimal", used, f"{name} still uses Decimal")


class BehaviourPreservedTests(unittest.TestCase):
    def test_csv_errors_and_values(self):
        head = "sku,name,price,quantity\n"
        (p,) = csvio.read_products(io.StringIO(head + 'A1,x,"$1,234.50",2\n'))
        self.assertEqual(p.price_cents, 123450)
        with self.assertRaises(ValidationError) as ctx:
            csvio.read_products(io.StringIO(head + "A1,x,1.00,1\nB2,y,abc,1\n"))
        self.assertEqual(str(ctx.exception), "row 2: invalid price: 'abc'")
        with self.assertRaises(ValidationError) as ctx:
            csvio.read_products(io.StringIO(head + "A1,x,-3,1\n"))
        self.assertEqual(str(ctx.exception), "row 1: invalid price: '-3'")

    def test_cli_bad_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.csv")
            for bad in ("abc", "1.005", "-2"):
                code, out, err = run(path, "add", "A1", "Pie", bad)
                self.assertEqual(code, 2, bad)
                self.assertIn(f"invalid price: {bad!r}", err)
                self.assertFalse(os.path.exists(path))

    def test_cli_accepts_same_inputs_as_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.csv")
            self.assertEqual(run(path, "add", "A1", "Pie", "$1,234.50", "--qty", "2")[0], 0)
            self.assertEqual(run(path, "add", "B2", "Mug", "7.5")[0], 0)
            self.assertEqual(run(path, "add", "C3", "Cup", "3")[0], 0)
            out = run(path, "list")[1]
            self.assertEqual(out.splitlines(), ["A1\tPie\t2\t$1,234.50", "B2\tMug\t0\t$7.50", "C3\tCup\t0\t$3.00"])


if __name__ == "__main__":
    unittest.main()
