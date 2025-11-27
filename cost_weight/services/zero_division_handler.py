from collections.abc import Mapping
from decimal import Decimal
from typing import Dict, Union

NumberLike = Union[str, float, int, Decimal]


def handle_zero_division(
    item_costs: Mapping[str, NumberLike],
    *,
    decimal_places: int = 2
) -> Dict[str, Decimal]:
    """
    Safely handles cases where the total cost is zero to prevent division errors.
    Returns 0.00 for each item if total cost = 0.
    """
    base = Decimal(1).scaleb(-decimal_places)

    # if empty input, return empty dict
    if not item_costs:
        return {}

    # convert everything to Decimal
    costs = {k: Decimal(str(v)) if not isinstance(v, Decimal) else v for k, v in item_costs.items()}
    total = sum(costs.values(), Decimal(0))

    if total == 0:
        return {k: Decimal("0.00").quantize(base) for k in costs}

    return None
