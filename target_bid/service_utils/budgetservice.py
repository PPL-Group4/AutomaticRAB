from decimal import Decimal
from target_bid.validators import TargetBudgetInput
from .converters import (
    ConversionStrategy,
    PercentageConversionStrategy,
    AbsoluteConversionStrategy,
)


class TargetBudgetConverter:
    """Delegates conversion to the appropriate strategy."""

    _strategies = {
        "percentage": PercentageConversionStrategy(),
        "absolute": AbsoluteConversionStrategy(),
    }

    @classmethod
    def to_nominal(cls, target_input: TargetBudgetInput, current_total: Decimal) -> Decimal:
        if not isinstance(current_total, Decimal):
            raise TypeError("Expected 'current_total' to be of type 'Decimal'.")

        strategy: ConversionStrategy = cls._strategies.get(target_input.mode)
        if not strategy:
            raise ValueError(f"Unsupported mode: {target_input.mode}")

        return strategy.convert(target_input, current_total)
