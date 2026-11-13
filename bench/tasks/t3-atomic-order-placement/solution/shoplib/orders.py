from __future__ import annotations

import threading
from typing import Iterable, Sequence

from .errors import OrderStateError, OutOfStock, UnknownOrder, ValidationError
from .inventory import Inventory
from .models import Order, OrderLine
from .pricing import Discount, apply_discounts, tax_cents


class OrderService:
    """Places and cancels orders against an inventory."""

    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory
        self._orders: dict[int, Order] = {}
        self._next_id = 1
        self._lock = threading.RLock()

    def place(self, items: Sequence[tuple[str, int]], discounts: Iterable[Discount] = ()) -> Order:
        """Place an order for ``(sku, qty)`` pairs and reserve the stock.

        The order is all-or-nothing: if any SKU lacks stock nothing is
        deducted and no order id is consumed. The same SKU may appear on
        several lines; their quantities are added up for the stock check.
        """
        if not items:
            raise ValidationError("an order needs at least one line")
        wanted: dict[str, int] = {}
        for sku, qty in items:
            if qty <= 0:
                raise ValidationError(f"quantity must be positive: {qty}")
            wanted[sku] = wanted.get(sku, 0) + qty
        with self._lock:
            for sku, qty in wanted.items():
                product = self.inventory.get(sku)
                if product.quantity < qty:
                    raise OutOfStock(sku, qty, product.quantity)
            lines = [OrderLine(sku, qty, self.inventory.get(sku).price_cents) for sku, qty in items]
            for sku, qty in wanted.items():
                self.inventory.remove_stock(sku, qty)
            order = Order(id=self._next_id, lines=lines, discounts=list(discounts))
            self._next_id += 1
            self._orders[order.id] = order
            return order

    def get(self, order_id: int) -> Order:
        try:
            return self._orders[order_id]
        except KeyError:
            raise UnknownOrder(order_id) from None

    def orders(self) -> list[Order]:
        return [self._orders[i] for i in sorted(self._orders)]

    def cancel(self, order_id: int) -> Order:
        """Cancel an order and return its units to stock."""
        with self._lock:
            order = self.get(order_id)
            if order.status == "cancelled":
                raise OrderStateError(f"order {order_id} is already cancelled")
            for line in order.lines:
                self.inventory.add_stock(line.sku, line.qty)
            order.status = "cancelled"
            return order

    def total_cents(self, order: Order) -> int:
        net = apply_discounts(order.subtotal_cents, order.discounts)
        return net + tax_cents(net)
