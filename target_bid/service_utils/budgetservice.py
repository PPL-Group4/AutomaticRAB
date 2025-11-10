from decimal import Decimal
from target_bid.validators import TargetBudgetInput
from .converters import (
    ConversionStrategy,
    PercentageConversionStrategy,
    AbsoluteConversionStrategy,
)

class TargetBudgetConverter:
    """Optimized version reducing lookups and redundant conversions."""

    _strategies = {
        "percentage": PercentageConversionStrategy(),
        "absolute": AbsoluteConversionStrategy(),
    }

    @classmethod
    def to_nominal(cls, target_input, current_total):
        if not isinstance(current_total, Decimal):
            raise TypeError("Expected 'current_total' to be of type 'Decimal'.")

        value = target_input.value
        if not isinstance(value, Decimal):
            value = Decimal(value)

        mode = target_input.mode
        if mode == "percentage":
            return (value / Decimal(100)) * current_total
        elif mode == "absolute":
            return value
        else:
            raise ValueError(f"Unsupported mode: {mode}")
