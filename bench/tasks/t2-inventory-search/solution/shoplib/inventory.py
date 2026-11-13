"""In-memory product inventory."""
from __future__ import annotations

from typing import Iterator, Optional

from .errors import OutOfStock, UnknownProduct, ValidationError
from .models import Product


class Inventory:
    """Holds products keyed by SKU and tracks their stock levels."""

    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    def __len__(self) -> int:
        return len(self._products)

    def __contains__(self, sku: object) -> bool:
        return sku in self._products

    def __iter__(self) -> Iterator[Product]:
        """Iterate over products sorted by SKU."""
        for sku in sorted(self._products):
            yield self._products[sku]

    def add_product(self, product: Product) -> None:
        """Register a new product. SKUs must be unique."""
        if product.sku in self._products:
            raise ValidationError(f"duplicate sku: {product.sku}")
        if product.price_cents < 0:
            raise ValidationError(f"negative price for {product.sku}")
        if product.quantity < 0:
            raise ValidationError(f"negative quantity for {product.sku}")
        self._products[product.sku] = product

    def get(self, sku: str) -> Product:
        """Return the product with this SKU or raise ``UnknownProduct``."""
        try:
            return self._products[sku]
        except KeyError:
            raise UnknownProduct(sku) from None

    def add_stock(self, sku: str, qty: int) -> int:
        """Add ``qty`` units to a product and return the new stock level."""
        if qty <= 0:
            raise ValidationError(f"quantity must be positive: {qty}")
        product = self.get(sku)
        product.quantity += qty
        return product.quantity

    def remove_stock(self, sku: str, qty: int) -> int:
        """Remove ``qty`` units and return the new stock level.

        Raises ``OutOfStock`` (and changes nothing) if there is not enough.
        """
        if qty <= 0:
            raise ValidationError(f"quantity must be positive: {qty}")
        product = self.get(sku)
        if product.quantity < qty:
            raise OutOfStock(sku, qty, product.quantity)
        product.quantity -= qty
        return product.quantity

    def search(self, query: str, category: Optional[str] = None) -> list[Product]:
        """Products whose name or SKU contains ``query`` (case-insensitive), sorted by SKU.

        If ``category`` is given, only products in that category match.
        """
        needle = query.lower()
        wanted = category.lower() if category is not None else None
        return [
            p for p in self
            if (needle in p.name.lower() or needle in p.sku.lower())
            and (wanted is None or p.category.lower() == wanted)
        ]

    def low_stock(self, threshold: int = 5) -> list[Product]:
        """Products with fewer than ``threshold`` units, sorted by SKU."""
        return [p for p in self if p.quantity < threshold]

    def total_value_cents(self) -> int:
        """Value of all stock at list price."""
        return sum(p.price_cents * p.quantity for p in self)

    def by_category(self) -> dict[str, list[Product]]:
        """Group products by category; each group is sorted by SKU."""
        groups: dict[str, list[Product]] = {}
        for product in self:
            groups.setdefault(product.category, []).append(product)
        return groups
