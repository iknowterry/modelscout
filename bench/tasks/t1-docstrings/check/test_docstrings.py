import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "shoplib" / "orders.py").read_text())


def public_nodes():
    for node in ast.walk(TREE):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            yield node


class DocstringTests(unittest.TestCase):
    def test_module_docstring(self):
        doc = ast.get_docstring(TREE)
        self.assertTrue(doc and len(doc.split()) >= 3)

    def test_public_definitions_documented(self):
        nodes = list(public_nodes())
        self.assertGreaterEqual(len(nodes), 6)
        for node in nodes:
            doc = ast.get_docstring(node)
            self.assertTrue(doc and len(doc.split()) >= 3, f"{node.name} needs a real docstring")

    def test_behaviour_unchanged(self):
        from shoplib.inventory import Inventory
        from shoplib.models import Product
        from shoplib.orders import OrderService
        inv = Inventory()
        inv.add_product(Product("A1", "Pie", 1000, 5))
        svc = OrderService(inv)
        order = svc.place([("A1", 2)])
        self.assertEqual(svc.total_cents(order), 2160)
        svc.cancel(order.id)
        self.assertEqual(inv.get("A1").quantity, 5)


if __name__ == "__main__":
    unittest.main()
