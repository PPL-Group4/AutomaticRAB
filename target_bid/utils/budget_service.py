from decimal import Decimal
from target_bid.validators import TargetBudgetInput
from typing import Iterable
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


def adjust_unit_prices_preserving_volume(items: Iterable, factor: Decimal):
    """
    Apply a proportional adjustment factor to unit prices and total prices,
    while ensuring that volume remains unchanged.
    """
    for item in items:
        original_volume = getattr(item, "volume", None)

        new_unit_price = (getattr(item, "unit_price", Decimal(0)) or Decimal(0)) * factor
        new_total = new_unit_price * (original_volume or Decimal(0))
        print(item.name, "old volume:", original_volume, "new unit:", new_unit_price, "new total:", new_total)

        # 🧩 Soft enforcement: detect if any code mutates volume
        assert getattr(item, "volume", None) == original_volume, (
            f"Volume changed unexpectedly for item '{getattr(item, 'name', '?')}'"
        )

        # Update recalculated fields
        item.unit_price = new_unit_price
        item.total_price = new_total
