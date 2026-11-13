import unittest

from shoplib.errors import OrderStateError, OutOfStock, UnknownOrder, UnknownProduct, ValidationError
from shoplib.inventory import Inventory
from shoplib.models import Product
from shoplib.orders import OrderService
from shoplib.pricing import percent_off


def make_service():
    inv = Inventory()
    inv.add_product(Product("A1", "Apple Pie", 1000, 5))
    inv.add_product(Product("B2", "Blue Mug", 500, 2))
    return OrderService(inv)


class PlaceTests(unittest.TestCase):
    def test_place_deducts_stock_and_numbers_orders(self):
        svc = make_service()
        first = svc.place([("A1", 2)])
        second = svc.place([("B2", 1)])
        self.assertEqual((first.id, second.id), (1, 2))
        self.assertEqual(svc.inventory.get("A1").quantity, 3)
        self.assertEqual(svc.inventory.get("B2").quantity, 1)

    def test_unit_price_is_frozen(self):
        svc = make_service()
        order = svc.place([("A1", 1)])
        svc.inventory.get("A1").price_cents = 9999
        self.assertEqual(order.lines[0].unit_price_cents, 1000)

    def test_out_of_stock(self):
        svc = make_service()
        with self.assertRaises(OutOfStock):
            svc.place([("B2", 3)])

    def test_unknown_product(self):
        with self.assertRaises(UnknownProduct):
            make_service().place([("ZZ", 1)])

    def test_empty_and_bad_quantity(self):
        svc = make_service()
        with self.assertRaises(ValidationError):
            svc.place([])
        with self.assertRaises(ValidationError):
            svc.place([("A1", 0)])

    def test_total_includes_discount_and_tax(self):
        svc = make_service()
        order = svc.place([("A1", 2), ("B2", 1)], discounts=[percent_off(10)])
        # subtotal 2500, 10% off -> 2250, tax 8% = 180
        self.assertEqual(svc.total_cents(order), 2430)

    def test_get_and_orders(self):
        svc = make_service()
        svc.place([("A1", 1)])
        svc.place([("A1", 1)])
        self.assertEqual([o.id for o in svc.orders()], [1, 2])
        with self.assertRaises(UnknownOrder):
            svc.get(99)


class CancelTests(unittest.TestCase):
    def test_cancel_restores_stock(self):
        svc = make_service()
        order = svc.place([("A1", 2), ("B2", 1)])
        svc.cancel(order.id)
        self.assertEqual(svc.inventory.get("A1").quantity, 5)
        self.assertEqual(svc.inventory.get("B2").quantity, 2)
        self.assertEqual(svc.get(order.id).status, "cancelled")

    def test_cancel_twice_fails(self):
        svc = make_service()
        order = svc.place([("A1", 1)])
        svc.cancel(order.id)
        with self.assertRaises(OrderStateError):
            svc.cancel(order.id)


if __name__ == "__main__":
    unittest.main()
