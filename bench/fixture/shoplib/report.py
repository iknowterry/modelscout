"""Plain-text sales and stock reports."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .inventory import Inventory
from .money import format_money
from .orders import OrderService


@dataclass(frozen=True)
class SalesSummary:
    """Aggregate numbers over all non-cancelled orders."""

    order_count: int
    units_sold: int
    revenue_cents: int
    top_skus: list[tuple[str, int]] = field(default_factory=list)


def summarize(service: OrderService, top_n: int = 3) -> SalesSummary:
    """Summarize the service's orders, ignoring cancelled ones.

    Revenue is the sum of each order's total including tax. ``top_skus``
    lists up to ``top_n`` ``(sku, units)`` pairs, most units first, with
    ties broken by SKU.
    """
    units_by_sku: Counter[str] = Counter()
    revenue = 0
    count = 0
    for order in service.orders():
        if order.status == "cancelled":
            continue
        count += 1
        revenue += service.total_cents(order)
        for line in order.lines:
            units_by_sku[line.sku] += line.qty
    ranked = sorted(units_by_sku.items(), key=lambda item: (-item[1], item[0]))
    return SalesSummary(count, sum(units_by_sku.values()), revenue, ranked[:top_n])


def format_summary(summary: SalesSummary) -> str:
    """Render a ``SalesSummary`` as a few lines of text."""
    lines = [
        f"Orders: {summary.order_count}",
        f"Units sold: {summary.units_sold}",
        f"Revenue: {format_money(summary.revenue_cents)}",
    ]
    if summary.top_skus:
        lines.append("Top products:")
        for rank, (sku, units) in enumerate(summary.top_skus, start=1):
            lines.append(f"  {rank}. {sku} - {units} units")
    return "\n".join(lines)


def stock_report(inventory: Inventory, threshold: int = 5) -> str:
    """One line per product (sorted by SKU) plus the total stock value.

    Products with fewer than ``threshold`` units are marked ``LOW``.
    """
    lines = []
    for product in inventory:
        flag = " LOW" if product.quantity < threshold else ""
        lines.append(f"{product.sku:<8} {product.name:<20} {product.quantity:>5}{flag}")
    lines.append(f"Total value: {format_money(inventory.total_value_cents())}")
    return "\n".join(lines)
