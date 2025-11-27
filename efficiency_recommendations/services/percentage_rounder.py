from decimal import ROUND_DOWN, Decimal
from typing import Dict, List


def round_weight_percentages(
    items: List[Dict],
    key: str = "weight_pct",
    ndigits: int = 2
) -> List[Dict]:
    if not items:
        return items

    step = Decimal(10) ** (-ndigits)        
    target = Decimal("100").quantize(step)

    raw = [Decimal(str(it.get(key, "0"))) for it in items]
    total_raw = sum(raw)

    if total_raw == 0:
        for it in items:
            it[key] = Decimal("0").quantize(step)
        return items

    floors = [v.quantize(step, rounding=ROUND_DOWN) for v in raw]
    remainders = [v - f for v, f in zip(raw, floors)]

    sum_floors = sum(floors)
    needed_steps = int(((target - sum_floors) / step).to_integral_value())  # could be 0

    order = sorted(
        range(len(items)),
        key=lambda i: (remainders[i], raw[i], Decimal(str(items[i].get("cost", "0")))),
        reverse=True,
    )

    rounded = floors[:]
    for k in range(max(0, needed_steps)):
        idx = order[k % len(items)]
        rounded[idx] = (rounded[idx] + step).quantize(step)

    # Write back
    for val, it in zip(rounded, items):
        it[key] = val
    return items