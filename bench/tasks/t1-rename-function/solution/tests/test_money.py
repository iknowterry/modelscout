import unittest

from shoplib.money import format_cents, round_half_up


class RoundHalfUpTests(unittest.TestCase):
    def test_halves_round_up(self):
        self.assertEqual(round_half_up("2.5"), 3)
        self.assertEqual(round_half_up("3.5"), 4)

    def test_below_half_rounds_down(self):
        self.assertEqual(round_half_up("2.49"), 2)

    def test_int_passthrough(self):
        self.assertEqual(round_half_up(7), 7)


class FormatMoneyTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(format_cents(1234), "$12.34")

    def test_thousands_separator(self):
        self.assertEqual(format_cents(123456), "$1,234.56")

    def test_zero_and_small(self):
        self.assertEqual(format_cents(0), "$0.00")
        self.assertEqual(format_cents(5), "$0.05")

    def test_negative(self):
        self.assertEqual(format_cents(-150), "-$1.50")


if __name__ == "__main__":
    unittest.main()
