from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, MutableMapping, Optional, TypedDict

from django.core.exceptions import ValidationError

from automatic_price_matching.total_cost import TotalCostCalculator

# ---------------------------------------------------------------------------
# Regex patterns for identifying numeric formatting variants & disallowed
# expression-like inputs (we explicitly reject multiplication / equations so
# the service never evaluates user supplied expressions).
# ---------------------------------------------------------------------------
_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")
_MULTIPLICATION_PATTERN = re.compile(r"\d+\s*[xX]\s*\d+")


# Typed representations -----------------------------------------------------
class _ComponentInput(TypedDict, total=False):  # noqa: D401 - internal helper
    """Loose structure of incoming component objects (all optional)."""

    code: Any
    name: Any
    type: Any
    coefficient: Any


class _ComponentCleaned(TypedDict):  # noqa: D401 - internal helper
    """Normalised component shape after validation."""

    code: str
    name: str
    type: str
    coefficient: Decimal


# Helper functions ---------------------------------------------------------
def _clean_string(
    errors: MutableMapping[str, List[str]],
    value: Any,
    field: str,
    *,
    required: bool = False,
) -> str:
    """Return a trimmed string or empty string while recording errors.

    Error wording intentionally mirrors the original implementation.
    """
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


def _append_number_error(
    errors: MutableMapping[str, List[str]], field: str, context: Optional[str] = None
) -> None:
    """Record a numeric coercion error with optional contextual prefix."""
    prefix = f"{context} " if context else ""
    errors[field].append(f"{prefix}must be numeric.")


def _normalise_numeric_string(candidate: str) -> str:
    """Normalise various thousand/decimal separator conventions to standard.

    Supported cases (examples):
      * 1.234,56  (European) -> 1234.56
      * 1,234.56  (US)       -> 1234.56
      * 1,234     (thousand commas, no decimals) -> 1234
      * 1,5       (comma as decimal) -> 1.5
      * Mixed patterns where the last separator indicates decimals.
    Non digit/plus/minus/dot characters are stripped afterwards.
    """
    if _THOUSAND_DOT_DECIMAL_COMMA.match(candidate):
        return candidate.replace(".", "").replace(",", ".")
    if _THOUSAND_COMMA_DECIMAL_DOT.match(candidate):
        return candidate.replace(",", "")

    if "," in candidate and "." not in candidate:
        return candidate.replace(",", ".")  # simple decimal comma
    if "," in candidate and "." in candidate:
        # Determine which separator appears last to infer decimal mark
        if candidate.rfind(",") > candidate.rfind("."):
            return candidate.replace(".", "").replace(",", ".")
        return candidate.replace(",", "")
    return candidate  # Already simple form


def _coerce_decimal(
    errors: MutableMapping[str, List[str]],
    value: Any,
    field: str,
    *,
    context: Optional[str] = None,
) -> Optional[Decimal]:
    """Attempt to coerce any supported numeric input to ``Decimal``.

    Returns ``None`` when the value is blank / None / not provided. Records an
    error (and returns None) when the input is syntactically present but not a
    valid number representation.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):  # Fast path
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))  # Avoid binary float artefacts
    if isinstance(value, str):
        candidate = value.strip()
        if candidate == "":
            return None
        if not any(ch.isdigit() for ch in candidate):
            _append_number_error(errors, field, context)
            return None
        if _MULTIPLICATION_PATTERN.search(candidate) or "=" in candidate:
            _append_number_error(errors, field, context)
            return None
        normalised = _normalise_numeric_string(candidate)
        # Strip any lingering unexpected characters (currency, spaces, etc.)
        normalised = re.sub(r"[^0-9.+-]", "", normalised)
        try:
            return Decimal(normalised)
        except InvalidOperation:
            _append_number_error(errors, field, context)
            return None

    # Fallback for unsupported types
    _append_number_error(errors, field, context)
    return None


def _clean_components(
    errors: MutableMapping[str, List[str]], raw_components: Any
) -> List[_ComponentCleaned]:
    """Validate and normalise the ``components`` list."""
    if raw_components in (None, ""):
        raw_components = []

    if not isinstance(raw_components, list):
        errors["components"].append("Must be a list of component objects.")
        return []

    cleaned_components: List[_ComponentCleaned] = []
    for index, component in enumerate(raw_components):
        if not isinstance(component, dict):
            errors["components"].append(
                f"Component at index {index} must be an object."
            )
            continue
        comp: _ComponentInput = component  # type: ignore[assignment]
        comp_clean: _ComponentCleaned = {
            "code": _clean_string(errors, comp.get("code"), "components", required=True),
            "name": _clean_string(errors, comp.get("name"), "components"),
            "type": _clean_string(errors, comp.get("type"), "components"),
            "coefficient": Decimal("0"),  # default, may be overwritten
        }
        if not comp_clean["code"]:
            errors["components"].append(f"Component at index {index} missing code.")

        coefficient = _coerce_decimal(
            errors,
            comp.get("coefficient"),
            "components",
            context=f"Component at index {index} coefficient",
        )
        if coefficient is not None:
            comp_clean["coefficient"] = coefficient

        cleaned_components.append(comp_clean)
    return cleaned_components


# Public API ---------------------------------------------------------------
def validate_ahsp_payload(payload: Any) -> Dict[str, Any]:
    """Validate and normalise a payload representing a single AHSP entry.

    Parameters
    ----------
    payload: Any
        Incoming object expected to be a ``dict`` with keys: code, name, unit,
        volume, unit_price, components.

    Returns
    -------
    dict
        Cleaned representation with numeric fields as ``Decimal``.
    """
    if payload is None:
        raise ValidationError({"__all__": ["AHSP payload cannot be null"]})
    if not isinstance(payload, dict):
        raise ValidationError({"__all__": ["AHSP payload must be a dictionary"]})

    errors: Dict[str, List[str]] = defaultdict(list)
    cleaned: Dict[str, Any] = {}

    # Simple string fields -------------------------------------------------
    cleaned["code"] = _clean_string(errors, payload.get("code"), "code", required=True)
    cleaned["name"] = _clean_string(errors, payload.get("name"), "name", required=True)
    cleaned["unit"] = _clean_string(errors, payload.get("unit"), "unit")

    # Volume (required presence) ------------------------------------------
    if "volume" not in payload:
        errors["volume"].append("This field is required.")
        cleaned["volume"] = None
    else:
        cleaned["volume"] = _coerce_decimal(errors, payload.get("volume"), "volume")

    # Optional numeric field
    cleaned["unit_price"] = _coerce_decimal(errors, payload.get("unit_price"), "unit_price")

    volume = cleaned.get("volume")
    unit_price = cleaned.get("unit_price")
    cleaned["total_cost"] = TotalCostCalculator.calculate(volume, unit_price)

    # Components ----------------------------------------------------------
    cleaned["components"] = _clean_components(errors, payload.get("components", []))

    # Final error check ---------------------------------------------------
    filtered_errors = {field: msgs for field, msgs in errors.items() if msgs}
    if filtered_errors:
        raise ValidationError(filtered_errors)
    return cleaned
