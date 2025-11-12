import csv
import logging
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from django.db.models import Q
from target_bid.models.scraped_product import (
    JuraganMaterialProduct,
    Mitra10Product,
    TokopediaProduct,
    GemilangProduct,
)

logger = logging.getLogger(__name__)

_NORMALIZED_DIR = Path(__file__).resolve().parents[1] / "normalized"


def _to_decimal(value) -> Decimal | None:
    try:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        text = str(value).strip()
        if not text:
            return None
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _normalise_name(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


@lru_cache(maxsize=1)
def _materials_catalog() -> Dict[int, Dict[str, str]]:
    path = _NORMALIZED_DIR / "materials.csv"
    catalog: Dict[int, Dict[str, str]] = {}
    if not path.exists():
        logger.warning("materials.csv not found at %s", path)
        return catalog
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    material_id = int(row.get("id", ""))
                except (ValueError, TypeError):
                    continue
                catalog[material_id] = {
                    "name": (row.get("name") or "").strip(),
                    "unit": (row.get("unit") or "").strip(),
                    "normalised_name": _normalise_name(row.get("name")),
                }
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load materials catalog from %s", path)
    return catalog


@lru_cache(maxsize=1)
def _material_brand_price_index() -> Dict[int, List[Dict[str, object]]]:
    path = _NORMALIZED_DIR / "material_brand_prices.csv"
    index: Dict[int, List[Dict[str, object]]] = {}
    if not path.exists():
        logger.info("material_brand_prices.csv not found at %s", path)
        return index
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    material_id = int(row.get("material_id", ""))
                except (ValueError, TypeError):
                    continue
                price = _to_decimal(row.get("unit_price"))
                if price is None:
                    continue
                index.setdefault(material_id, []).append(
                    {
                        "brand_name": (row.get("brand_name") or "").strip(),
                        "unit_price": price,
                        "is_default": row.get("is_default", "0") in {"1", "true", "True"},
                    }
                )
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load material brand prices from %s", path)
    return index


def _brand_price_alternatives(name: str, unit: str, current_price: Decimal) -> List[Dict[str, object]]:
    catalog = _materials_catalog()
    if not catalog:
        return []

    target_name = _normalise_name(name)
    unit_lower = (unit or "").strip().lower()
    candidates: List[Dict[str, object]] = []

    for material_id, data in catalog.items():
        if data.get("normalised_name") != target_name:
            continue
        material_unit = (data.get("unit") or "").strip().lower()
        if material_unit != unit_lower:
            continue
        for record in _material_brand_price_index().get(material_id, []):
            brand_price = record["unit_price"]
            if brand_price >= current_price:
                continue
            candidates.append(
                {
                    "name": data.get("name"),
                    "price": float(brand_price),
                    "unit": data.get("unit"),
                    "url": None,
                    "category": "brand_price",
                    "source": "material_brand_prices",
                    "brand": record.get("brand_name"),
                    "material_id": material_id,
                }
            )

    candidates.sort(key=lambda item: item["price"])
    return candidates


class ScrapedProductRepository:
    def __init__(self):
        self.sources = [
            JuraganMaterialProduct,
            Mitra10Product,
            TokopediaProduct,
            GemilangProduct,
        ]

    def find_cheaper_same_unit(self, name: str, unit: str, current_price: float, limit: int = 5) -> List[Dict]:
        """
        Search for cheaper alternatives with the same unit and similar name across all sources.
        """
        logger.info(
            "Searching cheaper alternatives for '%s' (unit=%s, price=%s)",
            name, unit, current_price,
        )

        price_decimal = _to_decimal(current_price) or Decimal("0")

        words = [w for w in name.split() if len(w) > 2][:3]  # pick first few useful words
        filters = Q(unit__iexact=unit) & Q(price__lt=price_decimal)

        results = []

        for model in self.sources:
            q = model.objects.using("scraper").filter(filters)
            for w in words:
                q = q.filter(name__icontains=w)
            items = q.values("name", "price", "unit", "url", "category")[:limit]
            for item in items:
                item["source"] = model._meta.db_table
                results.append(item)

        csv_alternatives = _brand_price_alternatives(name, unit, price_decimal)
        if csv_alternatives:
            logger.info("Adding %d brand price alternatives from CSV", len(csv_alternatives))
        results.extend(csv_alternatives)

        results.sort(key=lambda x: x["price"])
        logger.info("Found %d cheaper alternatives", len(results))
        return results[:limit]
