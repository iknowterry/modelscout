"""Money helpers. Every amount in shoplib is an integer number of cents."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Union

Number = Union[int, str, Decimal]


def round_half_up(value: Number) -> int:
    """Round ``value`` to the nearest integer; exact halves round up.

    Unlike the built-in ``round`` this never rounds to even, so 2.5 -> 3
    and 3.5 -> 4. Pass strings, ints or Decimals to avoid float noise.
    """
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_cents(cents: int) -> str:
    """Format integer cents for display, e.g. ``123456`` -> ``$1,234.56``."""
    sign = "-" if cents < 0 else ""
    dollars, rem = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rem:02d}"
