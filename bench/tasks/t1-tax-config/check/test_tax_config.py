import os
import pathlib
import re
import unittest
from decimal import Decimal
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TaxConfigTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if k != "SHOPLIB_TAX_RATE"}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_constant(self):
        from shoplib import config
        self.assertEqual(float(config.DEFAULT_TAX_RATE), 0.08)

    def test_default_rate(self):
        from shoplib.pricing import tax_cents
        self.assertEqual(tax_cents(10000), 800)

    def test_env_override_read_at_call_time(self):
        from shoplib.pricing import tax_cents
        self.assertEqual(tax_cents(10000), 800)
        os.environ["SHOPLIB_TAX_RATE"] = "0.10"
        self.assertEqual(tax_cents(10000), 1000)
        os.environ["SHOPLIB_TAX_RATE"] = "0.2"
        self.assertEqual(tax_cents(10000), 2000)
        del os.environ["SHOPLIB_TAX_RATE"]
        self.assertEqual(tax_cents(10000), 800)

    def test_explicit_rate_wins(self):
        from shoplib.pricing import tax_cents
        os.environ["SHOPLIB_TAX_RATE"] = "0.10"
        self.assertEqual(tax_cents(10000, Decimal("0.5")), 5000)

    def test_order_totals_follow_override(self):
        from shoplib.inventory import Inventory
        from shoplib.models import Product
        from shoplib.orders import OrderService
        inv = Inventory()
        inv.add_product(Product("A1", "Pie", 1000, 5))
        svc = OrderService(inv)
        order = svc.place([("A1", 1)])
        self.assertEqual(svc.total_cents(order), 1080)
        os.environ["SHOPLIB_TAX_RATE"] = "0.10"
        self.assertEqual(svc.total_cents(order), 1100)

    def test_literal_only_in_config(self):
        for path in (ROOT / "shoplib").glob("*.py"):
            if path.name == "config.py":
                continue
            self.assertIsNone(re.search(r"0\.08\b", path.read_text()), f"{path.name} still hardcodes 0.08")


if __name__ == "__main__":
    unittest.main()
