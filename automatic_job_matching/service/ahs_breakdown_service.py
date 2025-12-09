import csv
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from automatic_price_matching.normalization import canonicalize_job_code

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "target_bid" / "normalized"
_MONEY_QUANTUM = Decimal("0.01")
_QUANTITY_QUANTUM = Decimal("0.0001")
_COMPONENT_MAP = {"labor": "labor", "equipment": "equipment", "material": "materials"}


def _parse_decimal(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        logger.debug("Unable to parse decimal from value=%r", raw)
        return None


def _format_decimal(value: Optional[Decimal], quantum: Decimal) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.quantize(quantum, rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        logger.debug("Unable to quantize decimal value=%r", value)
        return float(value)

def _load_catalog(path: Path, *, extra_fields: Optional[List[str]] = None) -> Dict[str, Dict[str, object]]:
    extra_fields = extra_fields or []
    catalog: Dict[str, Dict[str, object]] = {}

    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                identifier = _extract_identifier(row)
                if not identifier:
                    continue

                entry = _build_entry(row, extra_fields)
                catalog[identifier] = entry

    except FileNotFoundError:
        logger.warning("Catalog file missing: %s", path)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load catalog from %s", path)

    return catalog

def _extract_identifier(row: Dict[str, str]) -> str:
    """Extract and normalize the row identifier."""
    return (row.get("id") or "").strip()


def _build_entry(row: Dict[str, str], extra_fields: List[str]) -> Dict[str, object]:
    """Build the catalog entry dictionary."""
    entry = {
        "code": _clean(row.get("code")),
        "name": _clean(row.get("name")),
        "unit": _clean(row.get("unit")),
        "unit_price": _parse_decimal(row.get("unit_price")),
    }

    for field in extra_fields:
        entry[field] = _clean(row.get(field))

    return entry


def _clean(value: Optional[str]) -> Optional[str]:
    """Strip whitespace and normalize empty values to None."""
    cleaned = (value or "").strip()
    return cleaned or None

@lru_cache(maxsize=1)
def _labor_catalog() -> Dict[str, Dict[str, object]]:
    return _load_catalog(_DATA_DIR / "labor.csv")


@lru_cache(maxsize=1)
def _equipment_catalog() -> Dict[str, Dict[str, object]]:
    return _load_catalog(_DATA_DIR / "equipment.csv")


@lru_cache(maxsize=1)
def _material_catalog() -> Dict[str, Dict[str, object]]:
    return _load_catalog(_DATA_DIR / "materials.csv", extra_fields=["brand"])


@lru_cache(maxsize=1)
def _ahs_main_catalog() -> Dict[str, Dict[str, object]]:
    catalog: Dict[str, Dict[str, object]] = {}
    path = _DATA_DIR / "ahs_main.csv"

    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                canonical = canonicalize_job_code(row.get("code"))
                if not canonical:
                    continue
                catalog[canonical] = {
                    "name": (row.get("name") or "").strip() or None,
                    "unit_price": _parse_decimal(row.get("unit_price")),
                }
    except FileNotFoundError:
        logger.warning("AHS main dataset missing: %s", path)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load AHS main dataset from %s", path)

    return catalog


@lru_cache(maxsize=1)
def _components_by_code() -> Dict[str, List[Dict[str, str]]]:
    components: Dict[str, List[Dict[str, str]]] = {}
    path = _DATA_DIR / "ahs_components.csv"

    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                canonical = canonicalize_job_code(row.get("ahs_code"))
                comp_type = (row.get("component_type") or "").strip().lower()
                component_id = (row.get("component_id") or "").strip()
                if not canonical or comp_type not in _COMPONENT_MAP or not component_id:
                    continue

                components.setdefault(canonical, []).append(
                    {
                        "component_type": comp_type,
                        "component_id": component_id,
                        "quantity": (row.get("quantity") or "").strip(),
                        "coefficient": (row.get("coefficient") or "").strip(),
                    }
                )
    except FileNotFoundError:
        logger.warning("AHS components dataset missing: %s", path)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load AHS components dataset from %s", path)

    return components
def get_ahs_breakdown(ahs_code: str) -> Optional[Dict[str, object]]:
    canonical = canonicalize_job_code(ahs_code)
    if not canonical:
        return None

    component_rows = _components_by_code().get(canonical)
    if not component_rows:
        return None

    catalogs = _load_catalogs()
    totals, details = _compute_component_totals(component_rows, catalogs)

    labor_total = totals["labor"]
    equipment_total = totals["equipment"]
    materials_total = totals["materials"]
    labor_equipment_total = labor_total + equipment_total
    overall_total = labor_equipment_total + materials_total

    main_entry = _ahs_main_catalog().get(canonical, {})

    return _format_breakdown(
        main_entry,
        labor_total,
        equipment_total,
        labor_equipment_total,
        materials_total,
        overall_total,
        details,
    )


# -----------------------------
# Helper functions
# -----------------------------

def _load_catalogs():
    return {
        "labor": _labor_catalog(),
        "equipment": _equipment_catalog(),
        "material": _material_catalog(),
    }


def _compute_component_totals(component_rows, catalogs):
    totals = {"labor": Decimal("0"), "equipment": Decimal("0"), "materials": Decimal("0")}
    details = {"materials": []}

    for row in component_rows:
        comp_type = row["component_type"]
        out_key = _COMPONENT_MAP[comp_type]
        catalog = catalogs[comp_type]

        quantity = _extract_quantity(row)
        unit_price = _get_unit_price(catalog, row["component_id"])
        total_cost = _compute_total_cost(quantity, unit_price)

        if total_cost is not None:
            totals[out_key] += total_cost

        if out_key == "materials":
            details["materials"].append(
                _build_material_detail(row, catalog.get(row["component_id"], {}), quantity, unit_price, total_cost)
            )

    return totals, details


def _extract_quantity(row):
    """Return quantity, falling back through multiple fields."""
    for key in ("quantity", "coefficient"):
        value = _parse_decimal(row.get(key))
        if value is not None:
            return value
    return Decimal("0")


def _get_unit_price(catalog, comp_id):
    entry = catalog.get(comp_id)
    return entry.get("unit_price") if entry else None


def _compute_total_cost(quantity, unit_price):
    if unit_price is None:
        return None
    return quantity * unit_price


def _build_material_detail(row, catalog_entry, quantity, unit_price, total_cost):
    return {
        "id": row["component_id"],
        "code": catalog_entry.get("code"),
        "name": catalog_entry.get("name"),
        "unit": catalog_entry.get("unit"),
        "quantity": _format_decimal(quantity, _QUANTITY_QUANTUM),
        "unit_price": _format_decimal(unit_price, _MONEY_QUANTUM),
        "total_cost": _format_decimal(total_cost, _MONEY_QUANTUM),
        "brand": catalog_entry.get("brand"),
    }


def _format_breakdown(
    main_entry,
    labor_total,
    equipment_total,
    labor_equipment_total,
    materials_total,
    overall_total,
    details,
):
    return {
        "name": main_entry.get("name"),
        "unit_price": _format_decimal(main_entry.get("unit_price"), _MONEY_QUANTUM),
        "totals": {
            "labor": _format_decimal(labor_total, _MONEY_QUANTUM),
            "equipment": _format_decimal(equipment_total, _MONEY_QUANTUM),
            "labor_equipment": _format_decimal(labor_equipment_total, _MONEY_QUANTUM),
            "materials": _format_decimal(materials_total, _MONEY_QUANTUM),
            "overall": _format_decimal(overall_total, _MONEY_QUANTUM),
        },
        "components": details,
    }
