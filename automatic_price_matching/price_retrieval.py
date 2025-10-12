from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Mapping, Optional, Protocol


def _canonicalise_code(code: str) -> str:
    """Normalise an AHSP job code to a canonical form.

    Rules:
    - Trim whitespace
    - Uppercase letters
    - Treat dash and dot as equivalent separators (canonical '.' used)
    - Collapse repeated separators
    """
    if not isinstance(code, str):  # guard for unexpected inputs
        return ""

    text = code.strip().upper()
    if not text:
        return ""

    # Replace common separators with '.'
    unified = (
        text.replace("-", ".")
        .replace(" ", ".")
        .replace("/", ".")
        .replace("_", ".")
    )

    # Collapse multiple dots and strip leading/trailing dots
    while ".." in unified:
        unified = unified.replace("..", ".")
    return unified.strip(".")


class AhspSource(Protocol):
    """Abstract price source for AHSP codes."""

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        ...


class MockAhspSource:
    """In-memory AHSP code -> price mapping for tests and local dev.

    Accepts a mapping of possibly mixed numeric types and coerces values to Decimal.
    Keys are normalised to canonical form for case/separator-insensitive lookups.
    """

    def __init__(self, data: Mapping[str, Decimal | int | float | str]):
        self._store: Dict[str, Decimal] = {}
        for raw_code, raw_price in data.items():
            key = _canonicalise_code(raw_code)
            self._store[key] = (
                raw_price
                if isinstance(raw_price, Decimal)
                else Decimal(str(raw_price))
            )

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        # Ensure safety even if caller forgot to canonicalise
        key = _canonicalise_code(canonical_code)
        return self._store.get(key)


@dataclass
class AhspPriceRetriever:
    """Service to retrieve AHSP unit price by job code from a source."""

    source: AhspSource

    def get_price_by_job_code(self, code: object) -> Optional[Decimal]:
        # Type/blank guards per tests
        if not isinstance(code, str):
            return None
        canonical = _canonicalise_code(code)
        if not canonical:
            return None
        return self.source.get_price_by_code(canonical)
