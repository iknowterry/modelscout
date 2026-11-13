import unittest

from shoplib.errors import OutOfStock, UnknownProduct, ValidationError
from shoplib.inventory import Inventory
from shoplib.models import Product


def make_inventory():
    inv = Inventory()
    inv.add_product(Product("B2", "Blue Mug", 1200, 10, "kitchen"))
    inv.add_product(Product("A1", "Apple Pie", 850, 3, "food"))
    inv.add_product(Product("C3", "Cutting Board", 2500, 5, "kitchen"))
    return inv


class InventoryTests(unittest.TestCase):
    def test_iteration_is_sorted_by_sku(self):
        self.assertEqual([p.sku for p in make_inventory()], ["A1", "B2", "C3"])

    def test_duplicate_sku_rejected(self):
        inv = make_inventory()
        with self.assertRaises(ValidationError):
            inv.add_product(Product("A1", "Other", 100))

    def test_get_unknown(self):
        with self.assertRaises(UnknownProduct):
            make_inventory().get("ZZ")

    def test_add_and_remove_stock(self):
        inv = make_inventory()
        self.assertEqual(inv.add_stock("A1", 4), 7)
        self.assertEqual(inv.remove_stock("A1", 2), 5)

    def test_remove_too_much_changes_nothing(self):
        inv = make_inventory()
        with self.assertRaises(OutOfStock):
            inv.remove_stock("A1", 4)
        self.assertEqual(inv.get("A1").quantity, 3)

    def test_non_positive_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            make_inventory().add_stock("A1", 0)

    def test_low_stock_default_threshold(self):
        self.assertEqual([p.sku for p in make_inventory().low_stock()], ["A1"])

    def test_low_stock_custom_threshold(self):
        self.assertEqual([p.sku for p in make_inventory().low_stock(6)], ["A1", "C3"])

    def test_total_value(self):
        self.assertEqual(make_inventory().total_value_cents(), 1200 * 10 + 850 * 3 + 2500 * 5)

    def test_by_category(self):
        groups = make_inventory().by_category()
        self.assertEqual([p.sku for p in groups["kitchen"]], ["B2", "C3"])
        self.assertEqual([p.sku for p in groups["food"]], ["A1"])


if __name__ == "__main__":
    unittest.main()
