from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, List, Optional, Protocol, Sequence

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
    analysis_code: Optional[str]
    is_locked: Optional[bool] = None

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
            "analysis_code": self.analysis_code,
        }

class LockedItemRule:
    """Marks RAB job items as non-adjustable if they are flagged as locked/inflexible."""

    def decide(self, item: RabJobItem) -> Optional[bool]:
        # Some RAB models might store this as 'is_locked', 'locked', or 'inflexible'
        locked_flag = getattr(item, "is_locked", None)
        if locked_flag is True:
            return True
        return None


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
        raw_code = getattr(row, "analysis_code", None)
        analysis_code = (raw_code or "").strip() or None

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
            analysis_code=analysis_code,
            is_locked=getattr(row, "is_locked", False),
        )


class RabJobItemService:
    """Coordinator that fetches raw rows and maps them into domain objects."""

    def __init__(
        self,
        repository: RabItemRepository,
        mapper: RabJobItemMapper,
        non_adjustable_policy: Optional["NonAdjustableEvaluator"] = None,
    ) -> None:
        self._repository = repository
        self._mapper = mapper
        self._non_adjustable_policy = non_adjustable_policy or _DEFAULT_NON_ADJUSTABLE_POLICY

    def get_items(self, rab_id: int) -> List[RabJobItem]:
        rows = self._repository.for_rab(rab_id)
        mapped = [self._mapper.map(row) for row in rows]
        return [item for item in mapped if not self._non_adjustable_policy.is_non_adjustable(item)]


_NON_ADJUSTABLE_NAME_LOOKUP = {
    "rencana keselamatan konstruksi",
    "penyiapan dokumen penerapan smkk",
    "sosialisasi promosi dan pelatihan",
    "alat pelindung kerja apk",
    "alat pelindung kerja apk terdiri dari",
    "pembatas area",
    "alat pelindung diri apd",
    "alat pelindung diri apd terdiri dari",
    "helm pelindung",
    "sarung tangan",
    "kacamata pelindung",
    "sepatu keselamatan",
    "rompi keselamatan",
    "fasilitas sarana prasarana dan alat kesehatan",
    "peralatan p3k kotak p3k",
    "rambu dan perlengkapan lalu lintas",
    "alat pemadam api ringan apar",
}


_ROMAN_NUMERAL_PREFIX = re.compile(r"^(?:[0-9]+|[ivxlcdm]+)\s+", re.IGNORECASE)


class NameNormaliser:
    """Normalises job item names to simplify matching strategies."""

    def normalise(self, name: Optional[str]) -> str:
        if not name:
            return ""
        text = re.sub(r"[^0-9a-zA-Z]+", " ", name).strip().lower()
        text = _ROMAN_NUMERAL_PREFIX.sub("", text)
        return re.sub(r"\s+", " ", text)


class DecisionRule(Protocol):
    """Represents a filtering rule that may accept or reject an item."""

    def decide(self, item: RabJobItem) -> Optional[bool]:  # pragma: no cover - interface
        ...


class NameBlacklistRule:
    """Rejects job items whose normalised name appears in the blacklist."""

    def __init__(self, blacklist: Sequence[str], normaliser: NameNormaliser) -> None:
        self._blacklist = set(blacklist)
        self._normaliser = normaliser

    def decide(self, item: RabJobItem) -> Optional[bool]:
        normalised = self._normaliser.normalise(item.name)
        if normalised and normalised in self._blacklist:
            return True
        return None


class CustomAhsOverrideRule:
    """Allows custom AHS entries to remain adjustable regardless of codes."""

    def decide(self, item: RabJobItem) -> Optional[bool]:
        if item.custom_ahs_id is not None:
            return False
        return None


class AnalysisCodeRule:
    """Marks items that provide an analysis code as non-adjustable."""

    def decide(self, item: RabJobItem) -> Optional[bool]:
        if item.analysis_code:
            return True
        return None


class NonAdjustableEvaluator:
    """Evaluates items against an ordered list of decision rules."""

    def __init__(self, rules: Sequence[DecisionRule]) -> None:
        self._rules = list(rules)

    def is_non_adjustable(self, item: RabJobItem) -> bool:
        for rule in self._rules:
            decision = rule.decide(item)
            if decision is not None:
                return decision
        return False


_DEFAULT_NAME_NORMALISER = NameNormaliser()
_DEFAULT_NAME_RULE = NameBlacklistRule(_NON_ADJUSTABLE_NAME_LOOKUP, _DEFAULT_NAME_NORMALISER)
_DEFAULT_RULES: Sequence[DecisionRule] = (
    _DEFAULT_NAME_RULE,
    CustomAhsOverrideRule(),
    AnalysisCodeRule(),
    LockedItemRule(),
)
_DEFAULT_NON_ADJUSTABLE_POLICY = NonAdjustableEvaluator(_DEFAULT_RULES)


def _normalise_item_name(name: Optional[str]) -> str:
    return _DEFAULT_NAME_NORMALISER.normalise(name)


def _is_non_adjustable_by_name(name: Optional[str]) -> bool:
    return bool(_DEFAULT_NAME_RULE.decide(RabJobItem(
        rab_item_id=0,
        name=name or "",
        unit_name=None,
        unit_price=None,
        volume=None,
        total_price=None,
        rab_item_header_id=None,
        rab_item_header_name=None,
        custom_ahs_id=None,
        analysis_code=None,
    )))


def _is_non_adjustable(item: RabJobItem) -> bool:
    return _DEFAULT_NON_ADJUSTABLE_POLICY.is_non_adjustable(item)


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
