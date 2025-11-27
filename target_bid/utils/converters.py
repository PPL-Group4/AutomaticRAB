# target_bid/converters.py
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from target_bid.validators import TargetBudgetInput


class ConversionStrategy(ABC):
    """Abstract strategy for converting a target budget into nominal value."""

    @abstractmethod
    def convert(self, target_input: TargetBudgetInput, current_total: Decimal) -> Decimal:
        ...
# target_bid/converters.py (continued)

class PercentageConversionStrategy(ConversionStrategy):
    def convert(self, target_input: TargetBudgetInput, current_total: Decimal) -> Decimal:
        return (current_total * target_input.value / Decimal("100")).quantize(Decimal("0.01"))


class AbsoluteConversionStrategy(ConversionStrategy):
    def convert(self, target_input: TargetBudgetInput, current_total: Decimal) -> Decimal:
        return target_input.value.quantize(Decimal("0.01"))
