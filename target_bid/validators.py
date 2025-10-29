from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, MutableMapping, Optional

from django.core.exceptions import ValidationError


# Thousand/decimal separator patterns reused from other validators in the project.
_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")


@dataclass(frozen=True)
class TargetBudgetInput:
    """Normalised representation of the target budget entry."""

    mode: str
    value: Decimal


def _normalise_mode(mode: Any) -> Optional[str]:
    if not isinstance(mode, str):
        return None
    key = mode.strip().lower()
    if key in {"percent", "percentage", "%"}:
        return "percentage"
    if key in {"absolute", "currency", "rupiah", "idr", "value"}:
        return "absolute"
    return None


def _normalise_numeric_string(candidate: str) -> str:
    """Normalise thousand/decimal separators to standard dot-decimal format."""
    if _THOUSAND_DOT_DECIMAL_COMMA.match(candidate):
        return candidate.replace(".", "").replace(",", ".")
    if _THOUSAND_COMMA_DECIMAL_DOT.match(candidate):
        return candidate.replace(",", "")

    if "," in candidate and "." not in candidate:
        return candidate.replace(",", ".")
    if "," in candidate and "." in candidate:
        if candidate.rfind(",") > candidate.rfind("."):
            return candidate.replace(".", "").replace(",", ".")
        return candidate.replace(",", "")
    return candidate


def _coerce_decimal(
    value: Any,
    errors: MutableMapping[str, list[str]],
    field: str,
    *,
    strip_percent: bool,
) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        if strip_percent:
            text = text.replace("%", "")
        elif "%" in text:
            errors[field].append("Percentage input is not allowed when mode is absolute.")
            return None

        text = re.sub(r"(?i)rp|idr", "", text)
        text = text.replace(" ", "")
        text = text.replace("_", "")

        cleaned = re.sub(r"[^0-9.,+-]", "", text)
        if not any(ch.isdigit() for ch in cleaned):
            errors[field].append("Target budget must be a numeric value.")
            return None

        normalised = _normalise_numeric_string(cleaned)
        try:
            return Decimal(normalised)
        except InvalidOperation:
            errors[field].append("Target budget must be a numeric value.")
            return None

    errors[field].append("Target budget must be a numeric value.")
    return None


def validate_target_budget_input(value: Any, *, mode: Any) -> TargetBudgetInput:
    """Validate and normalise the target budget entry provided by the user."""
    errors: Dict[str, list[str]] = defaultdict(list)

    normalised_mode = _normalise_mode(mode)
    if normalised_mode is None:
        errors["mode"].append("Mode must be either 'percentage' or 'absolute'.")

    numeric_value = _coerce_decimal(
        value,
        errors,
        "target_budget",
        strip_percent=(normalised_mode == "percentage"),
    )

    if numeric_value is None:
        if not errors["target_budget"]:
            errors["target_budget"].append("Target budget is required.")
    else:
        if normalised_mode == "percentage":
            if numeric_value <= 0 or numeric_value > 100:
                errors["target_budget"].append(
                    "Percentage value must be between 0 and 100."
                )
        elif normalised_mode == "absolute":
            if numeric_value <= 0:
                errors["target_budget"].append("Target budget must be greater than zero.")

    filtered_errors = {key: msgs for key, msgs in errors.items() if msgs}
    if filtered_errors:
        raise ValidationError(filtered_errors)

    return TargetBudgetInput(mode=normalised_mode, value=numeric_value)
