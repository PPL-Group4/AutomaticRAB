from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Mapping, Union
from cost_weight.services.normalization import _normalize_weights

NumberLike = Union[str, float, int, Decimal]

__all__ = ["calculate_cost_weights", "format_weights", "_normalize_weights"]

def _to_decimal(x: NumberLike) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(str(x))  # avoid binary float artifacts
    return Decimal(x)


def calculate_cost_weights(
    item_costs: Mapping[str, NumberLike],
    *,
    decimal_places: int = 2,
) -> Dict[str, Decimal]:
    base = Decimal(1).scaleb(-decimal_places)  # e.g., 0.01 for 2 dp
    hundred = Decimal("100")

    # Convert inputs
    costs = {k: _to_decimal(v) for k, v in item_costs.items()}
    total = sum(costs.values(), Decimal(0))

    # Edge case: no cost at all
    if total == 0:
        return {k: Decimal(0).quantize(base) for k in costs}

    # Raw (unrounded) shares
    raw = {k: (cost / total) * hundred for k, cost in costs.items()}

    # Floor to the grid (base) first
    floored = {k: (raw[k] // base) * base for k in raw}
    sum_floor = sum(floored.values())

    # Remaining base units to reach exactly 100.xx
    remaining_units = int(
        ((hundred - sum_floor) / base).to_integral_value(rounding=ROUND_HALF_UP)
    )

    # Distribute leftover units to largest fractional remainders
    remainders = [(k, raw[k] - floored[k]) for k in raw]
    remainders.sort(key=lambda kv: kv[1], reverse=True)

    result = floored.copy()
    for i in range(remaining_units):
        k = remainders[i % len(remainders)][0]
        result[k] = result[k] + base

    # Explicit rounding and final micro-adjust (safety)
    for k in result:
        result[k] = result[k].quantize(base, rounding=ROUND_HALF_UP)

    diff = hundred - sum(result.values())
    if diff != 0:    # pragma: no cover
        first_key = next(iter(result))
        result[first_key] = (result[first_key] + diff).quantize(base)

    return result


def format_weights(weights: Mapping[str, Decimal], *, decimal_places: int = 2) -> Dict[str, str]:
    q = Decimal(1).scaleb(-decimal_places)
    return {k: v.quantize(q, rounding=ROUND_HALF_UP).to_eng_string() for k, v in weights.items()}
