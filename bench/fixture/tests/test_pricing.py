import unittest
from decimal import Decimal

from shoplib.errors import ValidationError
from shoplib.pricing import Discount, apply_discounts, fixed_off, percent_off, tax_cents


class DiscountTests(unittest.TestCase):
    def test_no_discounts(self):
        self.assertEqual(apply_discounts(5000, []), 5000)

    def test_single_percent(self):
        self.assertEqual(apply_discounts(5000, [percent_off(10)]), 4500)

    def test_single_fixed(self):
        self.assertEqual(apply_discounts(5000, [fixed_off(700)]), 4300)

    def test_fixed_never_goes_negative(self):
        self.assertEqual(apply_discounts(500, [fixed_off(900)]), 0)

    def test_full_percent(self):
        self.assertEqual(apply_discounts(1234, [percent_off(100)]), 0)

    def test_invalid_discounts(self):
        with self.assertRaises(ValidationError):
            Discount("bogus", 1)
        with self.assertRaises(ValidationError):
            percent_off(101)
        with self.assertRaises(ValidationError):
            fixed_off(-1)


class TaxTests(unittest.TestCase):
    def test_default_rate(self):
        self.assertEqual(tax_cents(10000), 800)

    def test_rounds_half_up(self):
        self.assertEqual(tax_cents(1250), 100)
        self.assertEqual(tax_cents(1262), 101)

    def test_explicit_rate(self):
        self.assertEqual(tax_cents(10000, Decimal("0.2")), 2000)


if __name__ == "__main__":
    unittest.main()
