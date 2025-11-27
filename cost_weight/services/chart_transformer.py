from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional


def to_chart_data(
    weights: Mapping[str, Decimal],
    names_by_id: Optional[Mapping[str, str]] = None,
    *,
    decimal_places: int = 1,
    sort_desc: bool = False
) -> List[Dict[str, float]]:
    """
    Convert {id: Decimal(weight)} -> [{'label': <name>, 'value': float}]
    """
    if not weights:
        return []

    q = Decimal(1).scaleb(-decimal_places)
    names_by_id = names_by_id or {}

    rows = []
    for _id, w in weights.items():
        label = names_by_id.get(str(_id), str(_id))
        rounded = w.quantize(q, rounding=ROUND_HALF_UP)
        rows.append({"label": label, "value": float(rounded)})

    if sort_desc:
        rows.sort(key=lambda r: r["value"], reverse=True)

    return rows