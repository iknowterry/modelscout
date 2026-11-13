import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RenameTests(unittest.TestCase):
    def test_new_name_works(self):
        from shoplib import money
        self.assertEqual(money.format_cents(123456), "$1,234.56")
        self.assertEqual(money.format_cents(-150), "-$1.50")
        self.assertEqual(money.format_cents(5), "$0.05")

    def test_old_name_is_gone(self):
        from shoplib import money
        self.assertFalse(hasattr(money, "format_money"))

    def test_no_leftover_references(self):
        files = list((ROOT / "shoplib").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
        files.append(ROOT / "README.md")
        for path in files:
            self.assertNotIn("format_money", path.read_text(), f"{path} still mentions format_money")

    def test_callers_still_work(self):
        from shoplib import report
        summary = report.SalesSummary(1, 2, 12345, [("A1", 2)])
        self.assertIn("Revenue: $123.45", report.format_summary(summary))
        from shoplib.inventory import Inventory
        from shoplib.models import Product
        inv = Inventory()
        inv.add_product(Product("A1", "Apple Pie", 850, 2))
        self.assertTrue(report.stock_report(inv).endswith("Total value: $17.00"))


if __name__ == "__main__":
    unittest.main()
