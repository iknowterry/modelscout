import io
import os
import tempfile
import unittest

from shoplib import csvio
from shoplib.errors import ValidationError
from shoplib.models import Product


class ReadTests(unittest.TestCase):
    def test_reads_rows(self):
        text = 'sku,name,price,quantity\nA1,Apple Pie,8.50,3\nB2,Blue Mug,"$1,200.00",10\n'
        products = csvio.read_products(io.StringIO(text))
        self.assertEqual([(p.sku, p.price_cents, p.quantity) for p in products],
                         [("A1", 850, 3), ("B2", 120000, 10)])

    def test_missing_column(self):
        with self.assertRaisesRegex(ValidationError, "missing column: quantity"):
            csvio.read_products(io.StringIO("sku,name,price\nA1,x,1\n"))

    def test_bad_price_reports_row(self):
        text = "sku,name,price,quantity\nA1,x,1.00,1\nB2,y,abc,1\n"
        with self.assertRaisesRegex(ValidationError, r"row 2: invalid price: 'abc'"):
            csvio.read_products(io.StringIO(text))

    def test_sub_cent_price_rejected(self):
        with self.assertRaises(ValidationError):
            csvio.read_products(io.StringIO("sku,name,price,quantity\nA1,x,1.005,1\n"))

    def test_bad_quantity(self):
        with self.assertRaisesRegex(ValidationError, "row 1: invalid quantity"):
            csvio.read_products(io.StringIO("sku,name,price,quantity\nA1,x,1.00,two\n"))


class WriteTests(unittest.TestCase):
    def test_write_then_read_round_trip(self):
        products = [Product("A1", "Apple Pie", 850, 3), Product("B2", "Blue Mug", 1205, 0)]
        buf = io.StringIO()
        csvio.write_products(products, buf)
        self.assertEqual(buf.getvalue().splitlines()[0], "sku,name,price,quantity,category")
        buf.seek(0)
        again = csvio.read_products(buf)
        self.assertEqual([(p.sku, p.name, p.price_cents, p.quantity) for p in again],
                         [("A1", "Apple Pie", 850, 3), ("B2", "Blue Mug", 1205, 0)])

    def test_catalog_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "catalog.csv")
            self.assertEqual(len(csvio.load_catalog(path)), 0)
            inv = csvio.load_catalog(path)
            inv.add_product(Product("A1", "Apple Pie", 850, 3))
            csvio.save_catalog(inv, path)
            self.assertEqual(csvio.load_catalog(path).get("A1").price_cents, 850)


if __name__ == "__main__":
    unittest.main()
