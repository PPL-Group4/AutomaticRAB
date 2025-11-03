from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional

from rencanakan_core.models import RabItem


@dataclass(frozen=True)
class RabJobItem:
    """Lightweight projection of a RAB item for target bid calculations."""

    rab_item_id: int
    name: str
    unit_name: Optional[str]
    unit_price: Optional[Decimal]
    volume: Optional[Decimal]
    total_price: Optional[Decimal]
    rab_item_header_id: Optional[int]
    rab_item_header_name: Optional[str]
    custom_ahs_id: Optional[int]

    def to_dict(self) -> dict:
        """Serialise the job item into JSON-safe primitives."""

        return {
            "id": self.rab_item_id,
            "name": self.name,
            "unit": self.unit_name,
            "unit_price": _decimal_to_string(self.unit_price),
            "volume": _decimal_to_string(self.volume),
            "total_price": _decimal_to_string(self.total_price),
            "rab_item_header_id": self.rab_item_header_id,
            "rab_item_header_name": self.rab_item_header_name,
            "custom_ahs_id": self.custom_ahs_id,
        }


def fetch_rab_job_items(
    rab_id: int,
    *,
    queryset: Optional[Iterable] = None,
) -> List[RabJobItem]:
    """Fetch job items and their unit prices for the given RAB."""

    # Allow dependency injection for deterministic tests by accepting a pre-built iterable.
    rows: Iterable = queryset if queryset is not None else _default_queryset(rab_id)
    items: List[RabJobItem] = []

    for row in rows:
        unit_name = getattr(getattr(row, "unit", None), "name", None)
        header = getattr(row, "rab_item_header", None)
        header_id = getattr(header, "id", None)
        header_name = getattr(header, "name", None)

        unit_price = _to_decimal(getattr(row, "price", None))
        volume = _to_decimal(getattr(row, "volume", None))
        total_price = _multiply_decimal(volume, unit_price)

        items.append(
            RabJobItem(
                rab_item_id=getattr(row, "id"),
                name=(getattr(row, "name", "") or ""),
                unit_name=unit_name,
                unit_price=unit_price,
                volume=volume,
                total_price=total_price,
                rab_item_header_id=header_id,
                rab_item_header_name=header_name,
                custom_ahs_id=getattr(row, "custom_ahs_id", None),
            )
        )

    return items


def _default_queryset(rab_id: int):
    """Build the default queryset with the relations needed downstream."""

    return (
        RabItem.objects.select_related("unit", "rab_item_header")
        .filter(rab_id=rab_id)
        .order_by("id")
    )


def _to_decimal(value: Optional[object]) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _multiply_decimal(
    left: Optional[Decimal], right: Optional[Decimal]
) -> Optional[Decimal]:
    if left is None or right is None:
        return None
    return left * right


def _decimal_to_string(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
