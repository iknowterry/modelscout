"""Exception types raised by shoplib."""
from __future__ import annotations


class ShopError(Exception):
    """Base class for every error shoplib raises on purpose."""


class ValidationError(ShopError, ValueError):
    """Input data (a price, a quantity, a CSV row) was not acceptable."""


class UnknownProduct(ShopError):
    """A SKU was looked up that the inventory does not contain."""

    def __init__(self, sku: str) -> None:
        super().__init__(f"unknown product: {sku}")
        self.sku = sku


class OutOfStock(ShopError):
    """More units were requested than the inventory holds."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"out of stock: {sku} (requested {requested}, available {available})")
        self.sku = sku
        self.requested = requested
        self.available = available


class UnknownOrder(ShopError):
    """An order id was looked up that does not exist."""

    def __init__(self, order_id: int) -> None:
        super().__init__(f"unknown order: {order_id}")
        self.order_id = order_id


class OrderStateError(ShopError):
    """An operation is not allowed in the order's current status."""
