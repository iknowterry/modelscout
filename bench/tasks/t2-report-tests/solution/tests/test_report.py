import unittest

from shoplib.inventory import Inventory
from shoplib.models import Product
from shoplib.orders import OrderService
from shoplib.pricing import percent_off
from shoplib.report import SalesSummary, format_summary, stock_report, summarize


def make_service():
    inv = Inventory()
    inv.add_product(Product("A1", "Apple Pie", 1000, 50))
    inv.add_product(Product("B2", "Blue Mug", 500, 50))
    inv.add_product(Product("C3", "Cutting Board", 2500, 50))
    inv.add_product(Product("D4", "Desk Lamp", 3000, 50))
    return OrderService(inv)


class SummarizeTests(unittest.TestCase):
    def test_empty(self):
        summary = summarize(make_service())
        self.assertEqual(summary, SalesSummary(0, 0, 0, []))

    def test_counts_units_and_revenue_with_tax(self):
        svc = make_service()
        svc.place([("A1", 2), ("B2", 1)])      # subtotal 2500 -> 2700 with tax
        svc.place([("C3", 1)])                  # 2500 -> 2700
        summary = summarize(svc)
        self.assertEqual(summary.order_count, 2)
        self.assertEqual(summary.units_sold, 4)
        self.assertEqual(summary.revenue_cents, 5400)

    def test_discounts_reduce_revenue(self):
        svc = make_service()
        svc.place([("A1", 2)], discounts=[percent_off(50)])   # 1000 -> 1080
        self.assertEqual(summarize(svc).revenue_cents, 1080)

    def test_cancelled_orders_are_ignored(self):
        svc = make_service()
        svc.place([("A1", 1)])
        gone = svc.place([("B2", 7)])
        svc.cancel(gone.id)
        summary = summarize(svc)
        self.assertEqual((summary.order_count, summary.units_sold, summary.revenue_cents), (1, 1, 1080))
        self.assertEqual(summary.top_skus, [("A1", 1)])

    def test_units_are_summed_across_orders_and_lines(self):
        svc = make_service()
        svc.place([("A1", 1), ("A1", 2)])
        svc.place([("A1", 4)])
        self.assertEqual(summarize(svc).top_skus, [("A1", 7)])

    def test_top_skus_ranked_by_units_then_sku(self):
        svc = make_service()
        svc.place([("D4", 2), ("B2", 2), ("A1", 2), ("C3", 5)])
        self.assertEqual(summarize(svc, top_n=10).top_skus,
                         [("C3", 5), ("A1", 2), ("B2", 2), ("D4", 2)])

    def test_top_n_limits_results(self):
        svc = make_service()
        svc.place([("A1", 1), ("B2", 2), ("C3", 3), ("D4", 4)])
        self.assertEqual(summarize(svc).top_skus, [("D4", 4), ("C3", 3), ("B2", 2)])
        self.assertEqual(summarize(svc, top_n=1).top_skus, [("D4", 4)])
        self.assertEqual(summarize(svc, top_n=0).top_skus, [])


class FormatSummaryTests(unittest.TestCase):
    def test_full_format(self):
        summary = SalesSummary(3, 12, 123456, [("A1", 7), ("B2", 5)])
        self.assertEqual(format_summary(summary), "\n".join([
            "Orders: 3",
            "Units sold: 12",
            "Revenue: $1,234.56",
            "Top products:",
            "  1. A1 - 7 units",
            "  2. B2 - 5 units",
        ]))

    def test_no_top_products_section_when_empty(self):
        self.assertEqual(format_summary(SalesSummary(0, 0, 0, [])),
                         "Orders: 0\nUnits sold: 0\nRevenue: $0.00")

    def test_end_to_end(self):
        svc = make_service()
        svc.place([("A1", 1)])
        self.assertEqual(format_summary(summarize(svc)).splitlines()[2], "Revenue: $10.80")


class StockReportTests(unittest.TestCase):
    def make(self):
        inv = Inventory()
        inv.add_product(Product("B2", "Blue Mug", 500, 5))
        inv.add_product(Product("A1", "Apple Pie", 1000, 4))
        inv.add_product(Product("C3", "Cutting Board", 2500, 0))
        return inv

    def test_empty_inventory(self):
        self.assertEqual(stock_report(Inventory()), "Total value: $0.00")

    def test_rows_sorted_with_low_flag_and_total(self):
        lines = stock_report(self.make()).splitlines()
        self.assertEqual(lines[0], "A1       Apple Pie                4 LOW")
        self.assertEqual(lines[1], "B2       Blue Mug                 5")
        self.assertEqual(lines[2], "C3       Cutting Board            0 LOW")
        self.assertEqual(lines[3], "Total value: $65.00")
        self.assertEqual(len(lines), 4)

    def test_threshold_boundary_is_strict(self):
        inv = self.make()
        self.assertNotIn("LOW", stock_report(inv, threshold=4).splitlines()[0])
        self.assertIn("LOW", stock_report(inv, threshold=5).splitlines()[0])
        self.assertNotIn("LOW", stock_report(inv, threshold=5).splitlines()[1])
        self.assertIn("LOW", stock_report(inv, threshold=6).splitlines()[1])

    def test_default_threshold_is_five(self):
        self.assertEqual(stock_report(self.make()), stock_report(self.make(), threshold=5))


if __name__ == "__main__":
    unittest.main()
