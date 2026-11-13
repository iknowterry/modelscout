import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "shoplib" / "csvio.py").read_text()


def functions():
    return [n for n in ast.walk(ast.parse(SRC)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def all_args(fn):
    a = fn.args
    return a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])


class TypeHintTests(unittest.TestCase):
    def test_functions_exist(self):
        names = {f.name for f in functions()}
        for expected in ("parse_price", "format_price", "read_products", "write_products",
                         "load_catalog", "save_catalog", "write_orders"):
            self.assertIn(expected, names)

    def test_every_parameter_annotated(self):
        for fn in functions():
            for arg in all_args(fn):
                if arg.arg in ("self", "cls"):
                    continue
                self.assertIsNotNone(arg.annotation, f"{fn.name}({arg.arg}) has no annotation")

    def test_every_return_annotated(self):
        for fn in functions():
            self.assertIsNotNone(fn.returns, f"{fn.name} has no return annotation")

    def test_specific_return_types(self):
        by_name = {f.name: ast.unparse(f.returns) for f in functions()}
        self.assertEqual(by_name["parse_price"], "int")
        self.assertEqual(by_name["format_price"], "str")
        self.assertIn("Product", by_name["read_products"])
        self.assertIn("Inventory", by_name["load_catalog"])
        for name in ("write_products", "save_catalog", "write_orders"):
            self.assertEqual(by_name[name], "None")

    def test_no_any(self):
        for fn in functions():
            annotations = [ast.unparse(a.annotation) for a in all_args(fn) if a.annotation] + [ast.unparse(fn.returns)]
            for text in annotations:
                self.assertNotIn("Any", text, f"{fn.name} uses Any")

    def test_behaviour_unchanged(self):
        import io
        from shoplib import csvio
        self.assertEqual(csvio.parse_price("$1,234.50"), 123450)
        self.assertEqual(csvio.format_price(1205), "12.05")
        products = csvio.read_products(io.StringIO("sku,name,price,quantity\nA1,Pie,8.50,3\n"))
        self.assertEqual((products[0].sku, products[0].price_cents, products[0].quantity), ("A1", 850, 3))


if __name__ == "__main__":
    unittest.main()
