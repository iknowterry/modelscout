"""Discounts and tax. All results are integer cents."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence, Union

from .errors import ValidationError
from .money import round_half_up


@dataclass(frozen=True)
class Discount:
    """Either a percentage (``kind="percent"``) or a fixed amount in cents."""

    kind: str
    value: Union[int, float, Decimal]

    def __post_init__(self) -> None:
        if self.kind not in ("percent", "fixed"):
            raise ValidationError(f"unknown discount kind: {self.kind!r}")
        if self.value < 0:
            raise ValidationError("discount value must not be negative")
        if self.kind == "percent" and self.value > 100:
            raise ValidationError("percent discount must be at most 100")


def percent_off(pct: Union[int, float, Decimal]) -> Discount:
    """A discount of ``pct`` percent."""
    return Discount("percent", pct)


def fixed_off(cents: int) -> Discount:
    """A discount of a fixed number of cents."""
    return Discount("fixed", cents)


def apply_discounts(subtotal_cents: int, discounts: Sequence[Discount]) -> int:
    """Apply ``discounts`` in order and return the discounted total in cents."""
    total = subtotal_cents
    for discount in discounts:
        if discount.kind == "percent":
            cut = round(subtotal_cents * float(discount.value) / 100)
        else:
            cut = int(discount.value)
        total = max(0, total - cut)
    return total


def tax_cents(amount_cents: int, rate: Optional[Decimal] = None) -> int:
    """Sales tax on ``amount_cents``, rounded half up.

    ``rate`` is a fraction (0.08 means 8%). The default rate is 8%.
    """
    if rate is None:
        rate = Decimal("0.08")
    return round_half_up(Decimal(amount_cents) * Decimal(str(rate)))
