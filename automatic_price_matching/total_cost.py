from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Protocol, Tuple


class CostOperandsValidator(Protocol):
    """Validate inputs and return ready-to-use Decimal operands."""

    def validate(
        self, volume: Optional[Decimal], unit_price: Optional[Decimal]
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """Return validated operands or ``None`` when validation fails."""


class DecimalOperandsValidator:
    """Guard total cost calculation by enforcing Decimal operands."""

    def validate(
        self, volume: Optional[Decimal], unit_price: Optional[Decimal]
    ) -> Optional[Tuple[Decimal, Decimal]]:
        if not isinstance(volume, Decimal) or not isinstance(unit_price, Decimal):
            return None
        return volume, unit_price


class CostAggregator(Protocol):
    """Aggregate validated operands into a raw total value."""

    def aggregate(self, volume: Decimal, unit_price: Decimal) -> Decimal:
        """Compute the raw total prior to rounding."""


class MultiplicativeCostAggregator:
    """Default aggregator: multiply volume by unit price."""

    def aggregate(self, volume: Decimal, unit_price: Decimal) -> Decimal:
        return volume * unit_price


class RoundingStrategy(Protocol):
    """Define rounding behaviour for the aggregated total."""

    def round(self, value: Decimal) -> Decimal:
        """Apply rounding rules to ``value`` and return the adjusted Decimal."""


class HalfUpRoundingStrategy:
    """Quantize totals using Decimal's ROUND_HALF_UP semantics."""

    def __init__(self, precision: Decimal) -> None:
        self._precision = precision

    def round(self, value: Decimal) -> Decimal:
        return value.quantize(self._precision, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TotalCostCalculator:
    """Compose validation, aggregation, and rounding for total cost."""

    validator: CostOperandsValidator = field(default_factory=DecimalOperandsValidator)
    aggregator: CostAggregator = field(default_factory=MultiplicativeCostAggregator)
    rounding: RoundingStrategy = field(
        default_factory=lambda: HalfUpRoundingStrategy(Decimal("0.01"))
    )

    def compute(
        self, volume: Optional[Decimal], unit_price: Optional[Decimal]
    ) -> Optional[Decimal]:
        operands = self.validator.validate(volume, unit_price)
        if operands is None:
            return None

        raw_total = self.aggregator.aggregate(*operands)
        return self.rounding.round(raw_total)

    @classmethod
    def calculate(
        cls, volume: Optional[Decimal], unit_price: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Backward-compatible entry point for existing callers."""

        return cls().compute(volume, unit_price)
