from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Mapping, Optional

def to_chart_data(
    weights: Mapping[str, Decimal],
    names_by_id: Optional[Mapping[str, str]] = None,
    *,
    decimal_places: int = 1,
    sort_desc: bool = False
) -> List[Dict[str, float]]:
  
    # change mapping {item_id: Decimal(weight_pct)} to list chart-ready: [{label: 'jobItemName 62.5}, ...]
    if not weights:
        return []

    q = Decimal(1).scaleb(-decimal_places)  # 0.1 if 1 dp, 0.01 if 2
    names_by_id = names_by_id or {}

    rows = []
    for _id, w in weights.items():
        label = names_by_id.get(str(_id), str(_id))
        rounded = w.quantize(q, rounding=ROUND_HALF_UP)
        rows.append({"label": label, "value": float(rounded)})

    if sort_desc:
        rows.sort(key=lambda r: r["value"], reverse=True)

    return rows