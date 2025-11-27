from collections.abc import Mapping
from typing import Union

NumberLike = Union[int, float]

def validate_cost_inputs(item_costs: Mapping[str, NumberLike]) -> bool:
    if not isinstance(item_costs, dict):
        raise ValueError("Input must be a dictionary of items and costs.")

    for key, value in item_costs.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"Invalid type for cost value: {key} = {value}")
        if value < 0:
            raise ValueError(f"Negative cost detected: {key} = {value}")

    return True
