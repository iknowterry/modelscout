import contextlib
import io
import os
import tempfile
import unittest

from shoplib import cli


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "catalog.csv")

    def cat(self, *args):
        return run("--catalog", self.path, *args)

    def test_add_then_list(self):
        self.assertEqual(self.cat("add", "A1", "Apple Pie", "8.50", "--qty", "3")[0], 0)
        code, out, _ = self.cat("list")
        self.assertEqual(code, 0)
        self.assertEqual(out, "A1\tApple Pie\t3\t$8.50\n")

    def test_value(self):
        self.cat("add", "A1", "Apple Pie", "8.50", "--qty", "2")
        self.assertEqual(self.cat("value")[1], "Total inventory value: $17.00\n")

    def test_order_reduces_stock(self):
        self.cat("add", "A1", "Apple Pie", "10.00", "--qty", "5")
        code, out, _ = self.cat("order", "A1:2")
        self.assertEqual((code, out), (0, "order 1: $21.60\n"))
        self.assertIn("\t3\t", self.cat("list")[1])

    def test_out_of_stock_exit_code(self):
        self.cat("add", "A1", "Apple Pie", "10.00", "--qty", "1")
        code, _, err = self.cat("order", "A1:2")
        self.assertEqual(code, 2)
        self.assertIn("out of stock", err)

    def test_bad_price(self):
        code, _, err = self.cat("add", "A1", "x", "1.005")
        self.assertEqual(code, 2)
        self.assertIn("invalid price: '1.005'", err)


if __name__ == "__main__":
    unittest.main()
