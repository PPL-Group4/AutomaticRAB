from decimal import Decimal, DivisionByZero, InvalidOperation


class ProportionalAdjustmentCalculator:
    """Computes the proportional factor to scale RAB unit prices toward a target budget."""

    @staticmethod
    def compute(current_total: Decimal, target_total: Decimal) -> Decimal:
        """Return multiplier f = target_total / current_total."""
        # ---- Validation ----
        if not isinstance(current_total, Decimal) or not isinstance(target_total, Decimal):
            raise TypeError("Both 'current_total' and 'target_total' must be Decimal instances.")
        if current_total <= 0:
            raise ValueError("Current total must be positive and non-zero.")
        if target_total < 0:
            raise ValueError("Target total cannot be negative.")

        try:
            factor = target_total / current_total
        except (DivisionByZero, InvalidOperation):  # pragma: no cover
            raise ValueError("Cannot compute adjustment factor (division error).")
        # keep 4-decimal precision for proportional scaling
        return factor.quantize(Decimal("0.0001"))