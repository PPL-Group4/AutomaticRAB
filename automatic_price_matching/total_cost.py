from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


class TotalCostCalculator:
    """Compute total cost values with consistent rounding."""

    _quantize = Decimal("0.01")

    @classmethod
    def calculate(
        cls, volume: Optional[Decimal], unit_price: Optional[Decimal]
    ) -> Optional[Decimal]:
        if not isinstance(volume, Decimal) or not isinstance(unit_price, Decimal):
            return None

        return (volume * unit_price).quantize(cls._quantize, rounding=ROUND_HALF_UP)
