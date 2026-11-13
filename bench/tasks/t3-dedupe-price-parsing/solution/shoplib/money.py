"""Money helpers. Every amount in shoplib is an integer number of cents."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Union

from .errors import ValidationError

Number = Union[int, str, Decimal]


def round_half_up(value: Number) -> int:
    """Round ``value`` to the nearest integer; exact halves round up.

    Unlike the built-in ``round`` this never rounds to even, so 2.5 -> 3
    and 3.5 -> 4. Pass strings, ints or Decimals to avoid float noise.
    """
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_money(cents: int) -> str:
    """Format integer cents for display, e.g. ``123456`` -> ``$1,234.56``."""
    sign = "-" if cents < 0 else ""
    dollars, rem = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rem:02d}"


def parse_cents(text: str) -> int:
    """Parse a price such as ``12.34`` or ``$1,234.50`` into integer cents.

    Raises ``ValidationError`` for negatives, junk and sub-cent amounts.
    """
    cleaned = text.strip().lstrip("$").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValidationError(f"invalid price: {text!r}") from None
    cents = value * 100
    if not value.is_finite() or value < 0 or cents != cents.to_integral_value():
        raise ValidationError(f"invalid price: {text!r}")
    return int(cents)
