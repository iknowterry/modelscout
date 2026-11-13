import itertools
import unittest
from decimal import Decimal
from fractions import Fraction

from shoplib.pricing import Discount, apply_discounts, fixed_off, percent_off
from shoplib.orders import OrderService
from shoplib.inventory import Inventory
from shoplib.models import Product


def reference(subtotal, discounts):
    """Exact-arithmetic model of the rules in the bug report."""
    total = subtotal
    for kind, value in discounts:
        if kind == "percent":
            exact = Fraction(total) * Fraction(str(value)) / 100
            cut = int(exact + Fraction(1, 2))        # floor(x + 1/2): halves round up
        else:
            cut = value
        total = max(0, total - cut)
    return total


def build(discounts):
    return [percent_off(v) if k == "percent" else fixed_off(v) for k, v in discounts]


class StackingTests(unittest.TestCase):
    def test_reported_examples(self):
        self.assertEqual(apply_discounts(10000, [percent_off(10), percent_off(20)]), 7200)
        self.assertEqual(apply_discounts(1001, [percent_off(50)]), 500)

    def test_each_discount_applies_to_running_total(self):
        self.assertEqual(apply_discounts(10000, [percent_off(50), percent_off(50)]), 2500)
        self.assertEqual(apply_discounts(10000, [percent_off(10), percent_off(10), percent_off(10)]), 7290)

    def test_order_matters_between_fixed_and_percent(self):
        self.assertEqual(apply_discounts(2000, [fixed_off(500), percent_off(10)]), 1350)
        self.assertEqual(apply_discounts(2000, [percent_off(10), fixed_off(500)]), 1300)

    def test_halves_round_up_not_to_even(self):
        # 12.5% of 1012 = 126.5 -> 127 off; 12.5% of 1004 = 125.5 -> 126 off
        self.assertEqual(apply_discounts(1012, [percent_off(12.5)]), 885)
        self.assertEqual(apply_discounts(1004, [percent_off(12.5)]), 878)
        # 50% of 1001 = 500.5 -> 501; 50% of 1003 = 501.5 -> 502
        self.assertEqual(apply_discounts(1003, [percent_off(50)]), 501)
        self.assertEqual(apply_discounts(5, [percent_off(50)]), 2)
        self.assertEqual(apply_discounts(1, [percent_off(50)]), 0)

    def test_rounding_happens_per_discount(self):
        # 1001 -> 50% off -> 500; then 50% of 500 = 250 -> 250
        self.assertEqual(apply_discounts(1001, [percent_off(50), percent_off(50)]), 250)
        # 999 -> 33.3333% ... use exact fractions
        self.assertEqual(apply_discounts(999, [percent_off(Decimal("33.5")), percent_off(10)]),
                         reference(999, [("percent", "33.5"), ("percent", 10)]))

    def test_fixed_floors_at_zero_and_later_discounts_stay_zero(self):
        self.assertEqual(apply_discounts(500, [fixed_off(900), percent_off(10)]), 0)
        self.assertEqual(apply_discounts(500, [fixed_off(900), fixed_off(5)]), 0)

    def test_no_discounts_and_empty(self):
        self.assertEqual(apply_discounts(1234, []), 1234)
        self.assertEqual(apply_discounts(0, [percent_off(10)]), 0)

    def test_matches_exact_model_on_a_grid(self):
        subtotals = [0, 1, 2, 3, 5, 99, 100, 101, 995, 1001, 1003, 1012, 1999, 2500, 123457, 10 ** 7 + 3]
        pcts = [("percent", 5), ("percent", 10), ("percent", 12.5), ("percent", 33), ("percent", 7.5),
                ("percent", 100), ("percent", 0), ("fixed", 250), ("fixed", 1)]
        for subtotal in subtotals:
            for combo in itertools.chain(
                    ([c] for c in pcts), itertools.permutations(pcts[:5], 2), itertools.permutations(pcts[2:7], 3)):
                with self.subTest(subtotal=subtotal, discounts=combo):
                    self.assertEqual(apply_discounts(subtotal, build(combo)), reference(subtotal, combo))

    def test_order_total_uses_stacking(self):
        inv = Inventory()
        inv.add_product(Product("A1", "Pie", 10000, 5))
        svc = OrderService(inv)
        order = svc.place([("A1", 1)], discounts=[percent_off(10), percent_off(20)])
        self.assertEqual(svc.total_cents(order), 7200 + 576)


if __name__ == "__main__":
    unittest.main()
