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

        """
        if not items:
            raise ValidationError("an order needs at least one line")
        order_id = self._next_id
        self._next_id += 1
        lines = []
        for sku, qty in items:
            if qty <= 0:
                raise ValidationError(f"quantity must be positive: {qty}")
            product = self.inventory.get(sku)
            if product.quantity < qty:
                raise OutOfStock(sku, qty, product.quantity)
            self.inventory.remove_stock(sku, qty)
            lines.append(OrderLine(sku, qty, product.price_cents))
        order = Order(id=order_id, lines=lines, discounts=list(discounts))
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
