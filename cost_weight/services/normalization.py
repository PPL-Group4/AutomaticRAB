from decimal import ROUND_HALF_UP, Decimal
from typing import Dict


def _normalize_weights(
    weights: Dict[str, Decimal],
    *,
    decimal_places: int = 2
) -> Dict[str, Decimal]:
    
    base = Decimal(1).scaleb(-decimal_places)
    total = sum(weights.values())

    if total == 0:
        return weights

    diff = Decimal("100.00") - total
    if diff == 0:
        return weights

    # pick the key with the largest weight for correction
    largest_key = max(weights, key=lambda k: weights[k])
    adjusted = weights.copy()
    adjusted[largest_key] = (adjusted[largest_key] + diff).quantize(base, rounding=ROUND_HALF_UP)

    # keep sanity within [0,100]
    for k, v in adjusted.items():
        adjusted[k] = min(max(v, Decimal("0.00")), Decimal("100.00"))

    return adjusted
