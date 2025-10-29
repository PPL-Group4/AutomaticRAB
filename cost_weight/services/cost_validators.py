from decimal import Decimal, InvalidOperation
from typing import Mapping, Union

NumberLike = Union[int, float, str, Decimal]

def validate_cost_inputs(item_costs: Mapping[str, NumberLike]) -> bool:
    if not isinstance(item_costs, dict):
        raise ValueError("Input must be a dictionary of items and costs.")
    for key, value in item_costs.items():
        # terima int/float/str/Decimal tapi tetap numeric & non-negatif
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid type for cost value: {key} = {value}")
        if dec < 0:
            raise ValueError(f"Negative cost detected: {key} = {value}")
    return True
