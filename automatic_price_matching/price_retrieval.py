from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Protocol

# --- DB model import ---
from rencanakan_core.models import Ahs

from .normalization import canonicalize_job_code

logger = logging.getLogger(__name__)


class AhspSource(Protocol):
    """Abstract price source for AHSP codes."""

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        ...


class MockAhspSource:
    """In-memory AHSP code -> price mapping for tests and local dev."""

    def __init__(self, data: Mapping[str, Decimal | int | float | str]):
        self._store: Dict[str, Decimal] = {}
        for raw_code, raw_price in data.items():
            if raw_code is None:
                continue
            key = canonicalize_job_code(raw_code)
            if not key:
                continue
            try:
                price = raw_price if isinstance(raw_price, Decimal) else Decimal(str(raw_price))
            except Exception:
                continue
            self._store[key] = price

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        key = canonicalize_job_code(canonical_code)
        return self._store.get(key)


class CsvAhspSource:
    """Load AHSP_CIPTA_KARYA.csv and provide unit prices by canonical code."""

    def __init__(self, csv_path: Path | None = None):
        base = Path(__file__).resolve().parent.parent
        self.csv_path = csv_path or (base / "automatic_job_matching" / "data" / "AHSP_CIPTA_KARYA.csv")
        self._store: Dict[str, Decimal] = {}
        self._loaded = False

    def _parse_price(self, raw: str) -> Optional[Decimal]:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        s = s.upper().replace("RP", "")
        s = s.replace("\u2009", "")
        s = s.strip()
        if s == "-" or not any(ch.isdigit() for ch in s):
            return None
        s = s.replace(".", "")
        s = s.replace(",", ".")
        import re
        s = re.sub(r"[^0-9\.\-]", "", s)
        if not s:
            return None
        try:
            return Decimal(s)
        except Exception:
            return None

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            import csv
            with open(self.csv_path, encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh, delimiter=";")
                for row in reader:
                    normalized = { (k or "").strip().upper(): (v or "").strip() for k, v in row.items() }
                    raw_code = normalized.get("NO") or normalized.get(";NO") or normalized.get("NO.") or normalized.get("1")
                    raw_price = normalized.get("HARGA SATUAN") or normalized.get("HARGA SAT")
                    if not raw_code:
                        continue
                    key = canonicalize_job_code(raw_code)
                    if not key:
                        continue
                    price = self._parse_price(raw_price)
                    if price is not None:
                        self._store[key] = price
            logger.debug("CsvAhspSource loaded %d entries from %s", len(self._store), self.csv_path)
        except FileNotFoundError:
            logger.debug("CsvAhspSource CSV file not found: %s", self.csv_path)
        except Exception:
            logger.exception("CsvAhspSource failed to load CSV: %s", self.csv_path)
        self._loaded = True

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        self._load()
        key = canonicalize_job_code(canonical_code)
        return self._store.get(key)


class DatabaseAhspSource:
    """Query ahs.unit_price by canonical job code."""

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        try:
            logger.debug("DatabaseAhspSource lookup canonical_code=%s", canonical_code)
            # try case-insensitive first, then exact
            obj = Ahs.objects.filter(code__iexact=canonical_code).first()
            if not obj:
                obj = Ahs.objects.filter(code=canonical_code).first()
            price = getattr(obj, "unit_price", None) if obj else None
            logger.debug("DatabaseAhspSource found code=%s price=%s", getattr(obj, "code", None), price)
            if price is not None:
                return Decimal(str(price))
        except Exception:
            logger.exception("DatabaseAhspSource lookup failed for %s", canonical_code)
        return None


class CombinedAhspSource:
    """Try DB then CSV for price lookup; attempt common code variants."""

    def __init__(self, db_source: DatabaseAhspSource | None = None, csv_source: CsvAhspSource | None = None):
        self.db = db_source or DatabaseAhspSource()
        self.csv = csv_source or CsvAhspSource()

    def _try_variants_in_db(self, canonical_code: str) -> Optional[Decimal]:
        variants = {
            canonical_code,
            canonical_code.replace(".", "-"),
            canonical_code.replace("-", "."),
            canonical_code.replace(".", "").replace("-", ""),
        }
        for v in variants:
            price = self.db.get_price_by_code(v)
            if price is not None:
                logger.debug("CombinedAhspSource: DB hit for variant=%s price=%s", v, price)
                return price
        return None

    def get_price_by_code(self, canonical_code: str) -> Optional[Decimal]:
        if not canonical_code:
            return None
        db_price = self._try_variants_in_db(canonical_code)
        csv_price: Optional[Decimal] = None
        try:
            csv_price = self.csv.get_price_by_code(canonical_code)
        except Exception:
            logger.exception("CombinedAhspSource: CSV lookup failed for %s", canonical_code)

        if csv_price is not None:
            if (
                db_price is not None
                and db_price.quantize(Decimal("0.01")) != csv_price.quantize(Decimal("0.01"))
            ):
                logger.info(
                    "CombinedAhspSource: Preferring CSV price %s over DB price %s for code=%s",
                    csv_price,
                    db_price,
                    canonical_code,
                )
            elif db_price is None:
                logger.debug("CombinedAhspSource: CSV hit for code=%s price=%s", canonical_code, csv_price)
            return csv_price

        return db_price


@dataclass
class AhspPriceRetriever:
    """Service to retrieve AHSP unit price by job code from a source."""

    source: AhspSource

    def get_price_by_job_code(self, code: object) -> Optional[Decimal]:
        if not isinstance(code, str):
            return None
        canonical = canonicalize_job_code(code)
        if not canonical:
            return None
        return self.source.get_price_by_code(canonical)