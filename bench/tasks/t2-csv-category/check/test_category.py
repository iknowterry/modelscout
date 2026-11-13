import io
import os
import tempfile
import unittest

from shoplib import csvio
from shoplib.errors import ValidationError
from shoplib.models import Product


class CategoryColumnTests(unittest.TestCase):
    def test_write_has_category_as_last_column(self):
        buf = io.StringIO()
        csvio.write_products([Product("A1", "Apple Pie", 850, 3, "food"),
                              Product("B2", "Blue Mug", 1205, 0)], buf)
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[0], "sku,name,price,quantity,category")
        self.assertEqual(lines[1], "A1,Apple Pie,8.50,3,food")
        self.assertEqual(lines[2], "B2,Blue Mug,12.05,0,general")

    def test_read_with_category(self):
        text = "sku,name,price,quantity,category\nA1,Apple Pie,8.50,3,food\nB2,Blue Mug,12.05,1,kitchen\n"
        products = csvio.read_products(io.StringIO(text))
        self.assertEqual([p.category for p in products], ["food", "kitchen"])
        self.assertEqual([p.price_cents for p in products], [850, 1205])

    def test_old_files_without_category_still_import(self):
        text = "sku,name,price,quantity\nA1,Apple Pie,8.50,3\n"
        (product,) = csvio.read_products(io.StringIO(text))
        self.assertEqual(product.category, "general")

    def test_empty_category_cell_is_general(self):
        text = "sku,name,price,quantity,category\nA1,Apple Pie,8.50,3,\n"
        (product,) = csvio.read_products(io.StringIO(text))
        self.assertEqual(product.category, "general")

    def test_missing_required_column_still_rejected(self):
        with self.assertRaisesRegex(ValidationError, "missing column: price"):
            csvio.read_products(io.StringIO("sku,name,quantity,category\nA1,x,1,food\n"))

    def test_round_trip_through_buffer(self):
        original = [Product("A1", "Apple Pie", 850, 3, "food"), Product("B2", "Blue Mug", 1205, 0, "kitchen")]
        buf = io.StringIO()
        csvio.write_products(original, buf)
        buf.seek(0)
        self.assertEqual(csvio.read_products(buf), original)

    def test_catalog_file_round_trip_and_error_rows_unchanged(self):
        from shoplib.inventory import Inventory
        inv = Inventory()
        inv.add_product(Product("A1", "Apple Pie", 850, 3, "food"))
        inv.add_product(Product("B2", "Blue Mug", 1205, 2))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.csv")
            csvio.save_catalog(inv, path)
            again = csvio.load_catalog(path)
        self.assertEqual([(p.sku, p.category) for p in again], [("A1", "food"), ("B2", "general")])
        with self.assertRaisesRegex(ValidationError, "row 1: invalid price"):
            csvio.read_products(io.StringIO("sku,name,price,quantity,category\nA1,x,zz,1,food\n"))


if __name__ == "__main__":
    unittest.main()
