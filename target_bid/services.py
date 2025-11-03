from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Protocol

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
            "unit_price": DecimalAdapter.to_string(self.unit_price),
            "volume": DecimalAdapter.to_string(self.volume),
            "total_price": DecimalAdapter.to_string(self.total_price),
            "rab_item_header_id": self.rab_item_header_id,
            "rab_item_header_name": self.rab_item_header_name,
            "custom_ahs_id": self.custom_ahs_id,
        }


class RabItemRepository(Protocol):
    """Abstraction for fetching RAB items, allows alternate data sources."""

    def for_rab(self, rab_id: int) -> Iterable[object]:  # pragma: no cover - interface only
        ...


class DjangoRabItemRepository:
    """Repository that pulls data from the Django ORM."""

    def for_rab(self, rab_id: int) -> Iterable[object]:
        return (
            RabItem.objects.select_related("unit", "rab_item_header")
            .filter(rab_id=rab_id)
            .order_by("id")
        )


class DecimalAdapter:
    """Utility helpers for decimal conversion and formatting."""

    @staticmethod
    def to_decimal(value: Optional[object]) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def multiply(left: Optional[Decimal], right: Optional[Decimal]) -> Optional[Decimal]:
        if left is None or right is None:
            return None
        return left * right

    @staticmethod
    def to_string(value: Optional[Decimal]) -> Optional[str]:
        if value is None:
            return None
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"


class RabJobItemMapper:
    """Transforms raw ORM objects into immutable RabJobItem aggregates."""

    def __init__(self, decimal_adapter: type[DecimalAdapter] = DecimalAdapter) -> None:
        self._decimal = decimal_adapter

    def map(self, row: object) -> RabJobItem:
        unit = getattr(row, "unit", None)
        header = getattr(row, "rab_item_header", None)

        unit_price = self._decimal.to_decimal(getattr(row, "price", None))
        volume = self._decimal.to_decimal(getattr(row, "volume", None))
        total_price = self._decimal.multiply(volume, unit_price)

        return RabJobItem(
            rab_item_id=getattr(row, "id"),
            name=(getattr(row, "name", "") or ""),
            unit_name=getattr(unit, "name", None),
            unit_price=unit_price,
            volume=volume,
            total_price=total_price,
            rab_item_header_id=getattr(header, "id", None),
            rab_item_header_name=getattr(header, "name", None),
            custom_ahs_id=getattr(row, "custom_ahs_id", None),
        )


class RabJobItemService:
    """Coordinator that fetches raw rows and maps them into domain objects."""

    def __init__(
        self,
        repository: RabItemRepository,
        mapper: RabJobItemMapper,
    ) -> None:
        self._repository = repository
        self._mapper = mapper

    def get_items(self, rab_id: int) -> List[RabJobItem]:
        rows = self._repository.for_rab(rab_id)
        return [self._mapper.map(row) for row in rows]


_DEFAULT_SERVICE = RabJobItemService(DjangoRabItemRepository(), RabJobItemMapper())


def fetch_rab_job_items(
    rab_id: int,
    *,
    service: Optional[RabJobItemService] = None,
    queryset: Optional[Iterable] = None,
) -> List[RabJobItem]:
    """Fetch job items and their unit prices for the given RAB.

    A queryset may be provided for backwards compatibility with callers that
    already have data in memory. Otherwise the provided service is used, which
    defaults to a Django-backed implementation.
    """

    if queryset is not None:
        mapper = RabJobItemMapper()
        return [mapper.map(row) for row in queryset]

    selected_service = service or _DEFAULT_SERVICE
    return selected_service.get_items(rab_id)


# Backwards compatibility exports retained for unit tests and other modules.
_to_decimal = DecimalAdapter.to_decimal
_multiply_decimal = DecimalAdapter.multiply
_decimal_to_string = DecimalAdapter.to_string
_default_queryset = DjangoRabItemRepository().for_rab
