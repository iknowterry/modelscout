"""Runtime configuration for shoplib."""
from __future__ import annotations

import os
from decimal import Decimal

DEFAULT_TAX_RATE = 0.08


def tax_rate() -> Decimal:
    """The sales tax rate as a fraction; ``SHOPLIB_TAX_RATE`` overrides the default."""
    override = os.environ.get("SHOPLIB_TAX_RATE")
    if override:
        return Decimal(override)
    return Decimal(str(DEFAULT_TAX_RATE))
