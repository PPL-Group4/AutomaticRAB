from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from django.core.exceptions import ValidationError

_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")
_MULTIPLICATION_PATTERN = re.compile(r"\d+\s*[xX]\s*\d+")


def validate_ahsp_payload(payload: Any) -> Dict[str, Any]:
    """Validate and normalise a payload representing a single AHSP entry."""
    if payload is None:
        raise ValidationError({"__all__": ["AHSP payload cannot be null"]})

    if not isinstance(payload, dict):
        raise ValidationError({"__all__": ["AHSP payload must be a dictionary"]})

    errors: Dict[str, List[str]] = defaultdict(list)
    cleaned: Dict[str, Any] = {}

    def _clean_string(value: Any, field: str, *, required: bool = False) -> str:
        if value is None:
            if required:
                errors[field].append("This field cannot be null.")
            return ""
        if not isinstance(value, str):
            errors[field].append("Expected a string value.")
            return ""

        text = value.strip()
        if required and not text:
            errors[field].append("This field cannot be blank.")
        return text

    def _append_number_error(field: str, context: str | None = None) -> None:
        prefix = f"{context} " if context else ""
        errors[field].append(f"{prefix}must be numeric.")

    def _coerce_decimal(value: Any, field: str, *, context: str | None = None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            candidate = value.strip()
            if candidate == "":
                return None
            if not any(ch.isdigit() for ch in candidate):
                _append_number_error(field, context)
                return None
            if _MULTIPLICATION_PATTERN.search(candidate) or "=" in candidate:
                _append_number_error(field, context)
                return None
            if _THOUSAND_DOT_DECIMAL_COMMA.match(candidate):
                normalised = candidate.replace(".", "").replace(",", ".")
            elif _THOUSAND_COMMA_DECIMAL_DOT.match(candidate):
                normalised = candidate.replace(",", "")
            else:
                if "," in candidate and "." not in candidate:
                    normalised = candidate.replace(",", ".")
                elif "," in candidate and "." in candidate:
                    if candidate.rfind(",") > candidate.rfind("."):
                        normalised = candidate.replace(".", "").replace(",", ".")
                    else:
                        normalised = candidate.replace(",", "")
                else:
                    normalised = candidate
            normalised = re.sub(r"[^0-9.+-]", "", normalised)
            try:
                return Decimal(normalised)
            except InvalidOperation:
                _append_number_error(field, context)
                return None

        _append_number_error(field, context)
        return None

    cleaned["code"] = _clean_string(payload.get("code"), "code", required=True)
    cleaned["name"] = _clean_string(payload.get("name"), "name", required=True)
    cleaned["unit"] = _clean_string(payload.get("unit"), "unit")

    if "volume" not in payload:
        errors["volume"].append("This field is required.")
        cleaned["volume"] = None
    else:
        cleaned["volume"] = _coerce_decimal(payload.get("volume"), "volume")

    cleaned["unit_price"] = _coerce_decimal(payload.get("unit_price"), "unit_price")

    raw_components = payload.get("components", [])
    cleaned_components: List[Dict[str, Any]] = []

    if raw_components in (None, ""):
        raw_components = []

    if not isinstance(raw_components, list):
        errors["components"].append("Must be a list of component objects.")
    else:
        for index, component in enumerate(raw_components):
            if not isinstance(component, dict):
                errors["components"].append(f"Component at index {index} must be an object.")
                continue

            comp_clean: Dict[str, Any] = {}

            comp_clean["code"] = _clean_string(component.get("code"), "components", required=True)
            if not comp_clean["code"]:
                errors["components"].append(f"Component at index {index} missing code.")

            comp_clean["name"] = _clean_string(component.get("name"), "components")
            comp_clean["type"] = _clean_string(component.get("type"), "components")

            coefficient = _coerce_decimal(component.get("coefficient"), "components", context=f"Component at index {index} coefficient")
            comp_clean["coefficient"] = coefficient if coefficient is not None else Decimal("0")

            cleaned_components.append(comp_clean)

    cleaned["components"] = cleaned_components

    filtered_errors = {field: msgs for field, msgs in errors.items() if msgs}
    if filtered_errors:
        raise ValidationError(filtered_errors)

    return cleaned
