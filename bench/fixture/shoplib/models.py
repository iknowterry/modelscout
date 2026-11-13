"""Plain data classes shared by the rest of the package."""
from __future__ import annotations

from dataclasses import dataclass, field

from .pricing import Discount


@dataclass
class Product:
    """A sellable item. ``quantity`` is the number of units in stock."""

    sku: str
    name: str
    price_cents: int
    quantity: int = 0
    category: str = "general"


@dataclass(frozen=True)
class OrderLine:
    """One line of an order; the unit price is frozen at order time."""

    sku: str
    qty: int
    unit_price_cents: int

    @property
    def line_total_cents(self) -> int:
        """Quantity times unit price, before any discounts."""
        return self.qty * self.unit_price_cents


@dataclass
class Order:
    """A placed order. ``status`` is ``"placed"`` or ``"cancelled"``."""

    id: int
    lines: list[OrderLine]
    discounts: list[Discount] = field(default_factory=list)
    status: str = "placed"

    @property
    def subtotal_cents(self) -> int:
        """Sum of all line totals, before discounts and tax."""
        return sum(line.line_total_cents for line in self.lines)

    @property
    def units(self) -> int:
        """Total number of units across all lines."""
        return sum(line.qty for line in self.lines)
