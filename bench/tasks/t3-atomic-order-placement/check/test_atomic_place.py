import threading
import unittest

from shoplib.errors import OutOfStock, ValidationError
from shoplib.inventory import Inventory
from shoplib.models import Product
from shoplib.orders import OrderService


def make_service(a1=5, b2=2, c3=10):
    inv = Inventory()
    inv.add_product(Product("A1", "Apple Pie", 1000, a1))
    inv.add_product(Product("B2", "Blue Mug", 500, b2))
    inv.add_product(Product("C3", "Cutting Board", 2500, c3))
    return OrderService(inv)


def stock(svc):
    return {p.sku: p.quantity for p in svc.inventory}


class AtomicityTests(unittest.TestCase):
    def test_later_line_out_of_stock_changes_nothing(self):
        svc = make_service()
        before = stock(svc)
        with self.assertRaises(OutOfStock):
            svc.place([("A1", 2), ("C3", 1), ("B2", 3)])
        self.assertEqual(stock(svc), before)
        self.assertEqual(svc.orders(), [])

    def test_failed_order_does_not_consume_an_id(self):
        svc = make_service()
        with self.assertRaises(OutOfStock):
            svc.place([("A1", 1), ("B2", 99)])
        first = svc.place([("A1", 1)])
        second = svc.place([("B2", 1)])
        self.assertEqual((first.id, second.id), (1, 2))

    def test_same_sku_on_several_lines_is_checked_in_total(self):
        svc = make_service(a1=5)
        with self.assertRaises(OutOfStock) as ctx:
            svc.place([("A1", 3), ("C3", 1), ("A1", 3)])
        self.assertEqual(ctx.exception.sku, "A1")
        self.assertEqual(stock(svc), {"A1": 5, "B2": 2, "C3": 10})
        self.assertEqual(svc.place([("A1", 1)]).id, 1)

    def test_same_sku_on_several_lines_within_stock_succeeds(self):
        svc = make_service(a1=5)
        order = svc.place([("A1", 3), ("A1", 2)])
        self.assertEqual(stock(svc)["A1"], 0)
        self.assertEqual(order.units, 5)
        self.assertEqual(svc.get(order.id), order)

    def test_validation_errors_do_not_consume_ids_or_stock(self):
        svc = make_service()
        for items in ([], [("A1", 1), ("B2", 0)], [("A1", 1), ("B2", -1)]):
            with self.assertRaises(ValidationError):
                svc.place(items)
        self.assertEqual(stock(svc), {"A1": 5, "B2": 2, "C3": 10})
        self.assertEqual(svc.place([("A1", 1)]).id, 1)

    def test_unknown_sku_midway_changes_nothing(self):
        from shoplib.errors import UnknownProduct
        svc = make_service()
        with self.assertRaises(UnknownProduct):
            svc.place([("A1", 1), ("NOPE", 1)])
        self.assertEqual(stock(svc)["A1"], 5)
        self.assertEqual(svc.place([("A1", 1)]).id, 1)

    def test_exact_stock_is_allowed(self):
        svc = make_service(b2=2)
        svc.place([("B2", 2)])
        self.assertEqual(stock(svc)["B2"], 0)
        with self.assertRaises(OutOfStock):
            svc.place([("B2", 1)])

    def test_prices_and_totals_still_right(self):
        svc = make_service()
        order = svc.place([("A1", 2), ("C3", 1)])
        self.assertEqual(order.subtotal_cents, 4500)
        self.assertEqual(svc.total_cents(order), 4860)


class ThreadSafetyTests(unittest.TestCase):
    def hammer(self, svc, items_for, workers):
        barrier = threading.Barrier(workers, timeout=30)
        results = [None] * workers

        def work(i):
            barrier.wait()
            try:
                results[i] = svc.place(items_for(i))
            except OutOfStock as exc:
                results[i] = exc

        threads = [threading.Thread(target=work, args=(i,)) for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.assertFalse(any(t.is_alive() for t in threads))
        return results

    def test_no_oversell_and_ids_are_sequential(self):
        svc = make_service(a1=10)
        results = self.hammer(svc, lambda i: [("A1", 1)], workers=40)
        placed = [r for r in results if not isinstance(r, OutOfStock)]
        failed = [r for r in results if isinstance(r, OutOfStock)]
        self.assertEqual(len(placed), 10)
        self.assertEqual(len(failed), 30)
        self.assertEqual(stock(svc)["A1"], 0)
        self.assertEqual(sorted(o.id for o in placed), list(range(1, 11)))
        self.assertEqual([o.id for o in svc.orders()], list(range(1, 11)))

    def test_multi_line_orders_under_contention_are_all_or_nothing(self):
        svc = make_service(a1=7, b2=7)
        results = self.hammer(svc, lambda i: [("A1", 1), ("B2", 1)], workers=30)
        placed = [r for r in results if not isinstance(r, OutOfStock)]
        self.assertEqual(len(placed), 7)
        self.assertEqual(stock(svc)["A1"], 0)
        self.assertEqual(stock(svc)["B2"], 0)
        self.assertEqual(sorted(o.id for o in placed), list(range(1, 8)))


if __name__ == "__main__":
    unittest.main()
