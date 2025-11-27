from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from automatic_job_matching.service.ahs_breakdown_service import get_ahs_breakdown
from target_bid.models.rab_job_item import DecimalAdapter
from target_bid.services.cheaper_price_service import get_cheaper_alternatives
from target_bid.utils.budget_service import TargetBudgetConverter
from target_bid.validators import TargetBudgetInput

_MONEY_QUANT = Decimal("0.01")
_QUANTITY_QUANT = Decimal("0.0001")


def _to_decimal(value: Any, *, quantum: Optional[Decimal] = None) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if quantum:
        decimal_value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
    return decimal_value


def _money(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return DecimalAdapter.to_string(value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP))


def _quantity(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return DecimalAdapter.to_string(value.quantize(_QUANTITY_QUANT, rounding=ROUND_HALF_UP))


def _format_alternative(candidate: Dict[str, Any], price: Decimal) -> Dict[str, Any]:
    payload = dict(candidate)
    payload["price"] = _money(price)  # store as formatted string for consistency
    return payload


def optimize_ahs_price(
    ahs_code: str,
    *,
    material_limit: int = 2,
    target_input: Optional[TargetBudgetInput] = None,
) -> Optional[Dict[str, Any]]:
    """Return a cost-optimised breakdown by swapping the priciest materials."""

    breakdown = get_ahs_breakdown(ahs_code)
    if not breakdown:
        return None

    components = breakdown.get("components", {})
    materials_data = components.get("materials", []) or []

    entries: List[Dict[str, Any]] = []
    for item in materials_data:
        quantity = _to_decimal(item.get("quantity"), quantum=_QUANTITY_QUANT)
        unit_price = _to_decimal(item.get("unit_price"), quantum=_MONEY_QUANT)
        original_total = _to_decimal(item.get("total_cost"), quantum=_MONEY_QUANT)
        if original_total is None and quantity is not None and unit_price is not None:
            original_total = (quantity * unit_price).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        if original_total is None:
            original_total = Decimal("0")

        entry = {
            "name": item.get("name"),
            "unit": item.get("unit"),
            "brand": item.get("brand"),
            "quantity": quantity,
            "unit_price": unit_price,
            "original_total_cost": original_total,
            "adjusted_unit_price": unit_price,
            "adjusted_total_cost": original_total,
            "saving": Decimal("0"),
            "alternative": None,
        }
        entries.append(entry)

    limit = material_limit if isinstance(material_limit, int) else 2
    if limit < 0:
        limit = 0
    if limit > 2:
        limit = 2

    eligible = [
        entry
        for entry in entries
        if entry["quantity"] not in (None, Decimal("0")) and entry["unit_price"] is not None
    ]
    eligible.sort(key=lambda e: e["original_total_cost"], reverse=True)
    selected = eligible[:limit]

    for entry in selected:
        current_price = entry["unit_price"]
        quantity = entry["quantity"]
        if current_price is None or quantity is None:
            continue

        alternatives = get_cheaper_alternatives(entry["name"] or "", entry["unit"] or "", float(current_price))
        chosen_alt = None
        chosen_price = None
        for candidate in alternatives:
            candidate_price = _to_decimal(candidate.get("price"), quantum=_MONEY_QUANT)
            if candidate_price is None:
                continue
            if candidate_price < current_price:
                chosen_alt = candidate
                chosen_price = candidate_price
                break

        if not chosen_alt or chosen_price is None:
            continue

        new_total = (quantity * chosen_price).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        saving = entry["original_total_cost"] - new_total
        if saving <= 0:
            continue

        entry["adjusted_unit_price"] = chosen_price
        entry["adjusted_total_cost"] = new_total
        entry["saving"] = saving.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        entry["alternative"] = _format_alternative(chosen_alt, chosen_price)

    materials_total_original = sum(entry["original_total_cost"] for entry in entries)
    materials_total_adjusted = sum(entry["adjusted_total_cost"] for entry in entries)
    total_saving = (materials_total_original - materials_total_adjusted).quantize(
        _MONEY_QUANT, rounding=ROUND_HALF_UP
    )

    totals = breakdown.get("totals", {})
    overall_original = _to_decimal(totals.get("overall"), quantum=_MONEY_QUANT)
    if overall_original is None:
        overall_original = materials_total_original

    overall_adjusted = (overall_original - total_saving).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    if overall_adjusted < Decimal("0"):
        overall_adjusted = Decimal("0")

    replacements = [
        {
            "name": entry["name"],
            "unit": entry["unit"],
            "quantity": _quantity(entry["quantity"]),
            "original_unit_price": _money(entry["unit_price"]),
            "new_unit_price": _money(entry["adjusted_unit_price"]),
            "original_total_cost": _money(entry["original_total_cost"]),
            "new_total_cost": _money(entry["adjusted_total_cost"]),
            "saving": _money(entry["saving"]),
            "alternative": entry["alternative"],
        }
        for entry in entries
        if entry["saving"] > Decimal("0")
    ]

    materials_payload = [
        {
            "name": entry["name"],
            "unit": entry["unit"],
            "brand": entry["brand"],
            "quantity": _quantity(entry["quantity"]),
            "original_unit_price": _money(entry["unit_price"]),
            "adjusted_unit_price": _money(entry["adjusted_unit_price"]),
            "original_total_cost": _money(entry["original_total_cost"]),
            "adjusted_total_cost": _money(entry["adjusted_total_cost"]),
            "saving": _money(entry["saving"]),
            "alternative": entry["alternative"],
        }
        for entry in entries
    ]

    result: Dict[str, Any] = {
        "ahs_code": ahs_code,
        "original_totals": {
            "materials": _money(materials_total_original),
            "overall": _money(overall_original),
        },
        "adjusted_totals": {
            "materials": _money(materials_total_adjusted),
            "overall": _money(overall_adjusted),
        },
        "total_saving": _money(total_saving),
        "replacements": replacements,
        "materials": materials_payload,
    }

    if target_input is not None:
        nominal_target = TargetBudgetConverter.to_nominal(target_input, overall_original)
        meets_before = overall_original <= nominal_target
        meets_after = overall_adjusted <= nominal_target
        remaining_gap = (overall_adjusted - nominal_target).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        if remaining_gap < Decimal("0"):
            remaining_gap = Decimal("0")
        result["target_budget"] = {
            "mode": target_input.mode,
            "value": _money(target_input.value),
            "nominal": _money(nominal_target),
            "met_before_adjustment": meets_before,
            "met_after_adjustment": meets_after,
            "remaining_gap": _money(remaining_gap),
        }

    return result
