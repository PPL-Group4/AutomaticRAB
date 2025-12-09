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


def _safe_strip(value: Optional[str]) -> Optional[str]:
    """Strip and return None if empty."""
    if not value:
        return None
    stripped = value.strip()
    return stripped if stripped else None


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


def _create_catalog_entry(row: Dict[str, str], extra_fields: List[str]) -> Dict[str, object]:
    """Create a catalog entry from a CSV row."""
    entry: Dict[str, object] = {
        "code": _safe_strip(row.get("code")),
        "name": _safe_strip(row.get("name")),
        "unit": _safe_strip(row.get("unit")),
        "unit_price": _parse_decimal(row.get("unit_price")),
    }
    
    for field in extra_fields:
        entry[field] = _safe_strip(row.get(field))
    
    return entry


def _load_catalog(path: Path, *, extra_fields: Optional[List[str]] = None) -> Dict[str, Dict[str, object]]:
    extra_fields = extra_fields or []
    catalog: Dict[str, Dict[str, object]] = {}

    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                identifier = _safe_strip(row.get("id"))
                if not identifier:
                    continue
                
                catalog[identifier] = _create_catalog_entry(row, extra_fields)
    except FileNotFoundError:
        logger.warning("Catalog file missing: %s", path)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load catalog from %s", path)

    return catalog


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
                    "name": _safe_strip(row.get("name")),
                    "unit_price": _parse_decimal(row.get("unit_price")),
                }
    except FileNotFoundError:
        logger.warning("AHS main dataset missing: %s", path)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to load AHS main dataset from %s", path)

    return catalog


def _safe_catalog_get(catalog_entry: Optional[Dict], key: str) -> Optional[object]:
    """Safely get a value from catalog entry."""
    return catalog_entry.get(key) if catalog_entry else None


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


def _get_component_quantity(row: Dict[str, str]) -> Decimal:
    """Extract quantity or coefficient from component row."""
    quantity = _parse_decimal(row.get("quantity"))
    if quantity is None:
        quantity = _parse_decimal(row.get("coefficient"))
    return quantity if quantity is not None else Decimal("0")


def _build_component_detail(row: Dict[str, str], catalog_entry: Optional[Dict], 
                            quantity: Decimal, unit_price: Optional[object],
                            total_cost: Optional[Decimal], comp_type: str) -> Dict[str, object]:
    """Build detail dictionary for a component."""
    detail = {
        "id": row["component_id"],
        "code": _safe_catalog_get(catalog_entry, "code"),
        "name": _safe_catalog_get(catalog_entry, "name"),
        "unit": _safe_catalog_get(catalog_entry, "unit"),
        "quantity": _format_decimal(quantity, _QUANTITY_QUANTUM),
        "unit_price": _format_decimal(unit_price, _MONEY_QUANTUM),
        "total_cost": _format_decimal(total_cost, _MONEY_QUANTUM),
    }
    
    if comp_type == "material":
        detail["brand"] = _safe_catalog_get(catalog_entry, "brand")
    
    return detail


def _get_catalog_for_type(comp_type: str, labor_catalog: Dict, 
                         equipment_catalog: Dict, material_catalog: Dict) -> Dict:
    """Get the appropriate catalog based on component type."""
    return {
        "labor": labor_catalog,
        "equipment": equipment_catalog,
        "material": material_catalog,
    }[comp_type]


def get_ahs_breakdown(ahs_code: str) -> Optional[Dict[str, object]]:
    canonical = canonicalize_job_code(ahs_code)
    if not canonical:
        return None

    component_rows = _components_by_code().get(canonical)
    if not component_rows:
        return None

    labor_catalog = _labor_catalog()
    equipment_catalog = _equipment_catalog()
    material_catalog = _material_catalog()

    totals = {
        "labor": Decimal("0"),
        "equipment": Decimal("0"),
        "materials": Decimal("0"),
    }

    details = {
        "labor": [],
        "equipment": [],
        "materials": [],
    }

    for row in component_rows:
        comp_type = row["component_type"]
        out_key = _COMPONENT_MAP[comp_type]

        catalog = _get_catalog_for_type(comp_type, labor_catalog, equipment_catalog, material_catalog)
        catalog_entry = catalog.get(row["component_id"], None)

        quantity = _get_component_quantity(row)
        unit_price_raw = _safe_catalog_get(catalog_entry, "unit_price")
        
        if isinstance(unit_price_raw, Decimal):
            unit_price: Optional[Decimal] = unit_price_raw
            total_cost: Optional[Decimal] = quantity * unit_price
        else:
            unit_price = None
            total_cost = None

        if total_cost is not None:
            totals[out_key] += total_cost

        detail = _build_component_detail(row, catalog_entry, quantity, unit_price, total_cost, comp_type)
        details[out_key].append(detail)

    # Compute totals
    labor_total = totals["labor"]
    equipment_total = totals["equipment"]
    materials_total = totals["materials"]
    labor_equipment_total = labor_total + equipment_total
    overall_total = labor_equipment_total + materials_total

    # Main AHS info
    main_entry = _ahs_main_catalog().get(canonical, {})

    breakdown = {
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

    return breakdown

