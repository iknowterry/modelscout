import pathlib
import unittest

from shoplib.inventory import Inventory
from shoplib.models import Product

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build():
    inv = Inventory()
    inv.add_product(Product("MUG-02", "Blue Mug", 1200, 10, "Kitchen"))
    inv.add_product(Product("PIE-01", "Apple Pie", 850, 3, "food"))
    inv.add_product(Product("MUG-01", "Red Mug", 1100, 4, "kitchen"))
    inv.add_product(Product("BRD-07", "Cutting Board", 2500, 5, "kitchen"))
    inv.add_product(Product("TEA-10", "Mugwort Tea", 400, 0, "food"))
    return inv


class SearchTests(unittest.TestCase):
    def skus(self, products):
        return [p.sku for p in products]

    def test_name_substring_case_insensitive(self):
        self.assertEqual(self.skus(build().search("mug")), ["MUG-01", "MUG-02", "TEA-10"])
        self.assertEqual(self.skus(build().search("APPLE")), ["PIE-01"])

    def test_sku_substring(self):
        self.assertEqual(self.skus(build().search("brd")), ["BRD-07"])
        self.assertEqual(self.skus(build().search("-0")), ["BRD-07", "MUG-01", "MUG-02", "PIE-01"])

    def test_name_or_sku_not_both_required(self):
        self.assertEqual(self.skus(build().search("tea")), ["TEA-10"])

    def test_category_filter_is_case_insensitive(self):
        self.assertEqual(self.skus(build().search("mug", category="KITCHEN")), ["MUG-01", "MUG-02"])
        self.assertEqual(self.skus(build().search("mug", category="food")), ["TEA-10"])

    def test_category_is_exact_not_substring(self):
        self.assertEqual(build().search("", category="kitch"), [])

    def test_empty_query(self):
        inv = build()
        self.assertEqual(self.skus(inv.search("")), ["BRD-07", "MUG-01", "MUG-02", "PIE-01", "TEA-10"])
        self.assertEqual(self.skus(inv.search("", category="food")), ["PIE-01", "TEA-10"])

    def test_no_match_and_returns_list(self):
        result = build().search("zzz")
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_returns_the_actual_products(self):
        inv = build()
        self.assertIs(inv.search("pie")[0], inv.get("PIE-01"))

    def test_tests_were_added(self):
        text = (ROOT / "tests" / "test_inventory.py").read_text()
        self.assertIn(".search(", text)


if __name__ == "__main__":
    unittest.main()
