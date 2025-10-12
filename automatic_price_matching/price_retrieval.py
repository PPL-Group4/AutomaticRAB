from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Mapping, Optional, Protocol

from .normalization import canonicalize_job_code


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
            key = canonicalize_job_code(raw_code)
            self._store[key] = (
                raw_price
                if isinstance(raw_price, Decimal)
                else Decimal(str(raw_price))
            )

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        # Ensure safety even if caller forgot to canonicalise
        key = canonicalize_job_code(canonical_code)
        return self._store.get(key)


@dataclass
class AhspPriceRetriever:
    """Service to retrieve AHSP unit price by job code from a source."""

    source: AhspSource

    def get_price_by_job_code(self, code: object) -> Optional[Decimal]:
        # Type/blank guards per tests
        if not isinstance(code, str):
            return None
        canonical = canonicalize_job_code(code)
        if not canonical:
            return None
        return self.source.get_price_by_code(canonical)
