import unittest

from shoplib.errors import OrderStateError, UnknownOrder
from shoplib.inventory import Inventory
from shoplib.models import Product
from shoplib.orders import OrderService


def make_service():
    inv = Inventory()
    inv.add_product(Product("A1", "Apple Pie", 1000, 10))
    inv.add_product(Product("B2", "Blue Mug", 500, 4))
    return OrderService(inv)


class CancelTests(unittest.TestCase):
    def test_cancel_restores_stock_and_marks_cancelled(self):
        svc = make_service()
        order = svc.place([("A1", 3), ("B2", 4)])
        self.assertEqual(svc.inventory.get("A1").quantity, 7)
        result = svc.cancel(order.id)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(svc.get(order.id).status, "cancelled")
        self.assertEqual(svc.inventory.get("A1").quantity, 10)
        self.assertEqual(svc.inventory.get("B2").quantity, 4)

    def test_same_sku_on_two_lines(self):
        svc = make_service()
        order = svc.place([("A1", 2), ("A1", 3)])
        svc.cancel(order.id)
        self.assertEqual(svc.inventory.get("A1").quantity, 10)

    def test_second_cancel_is_an_error_and_does_not_restock_twice(self):
        svc = make_service()
        order = svc.place([("A1", 3)])
        svc.cancel(order.id)
        with self.assertRaises(OrderStateError):
            svc.cancel(order.id)
        self.assertEqual(svc.inventory.get("A1").quantity, 10)

    def test_unknown_order(self):
        with self.assertRaises(UnknownOrder):
            make_service().cancel(99)

    def test_other_orders_untouched(self):
        svc = make_service()
        first = svc.place([("A1", 1)])
        second = svc.place([("A1", 2)])
        svc.cancel(first.id)
        self.assertEqual(svc.get(second.id).status, "placed")
        self.assertEqual(svc.inventory.get("A1").quantity, 8)


if __name__ == "__main__":
    unittest.main()
