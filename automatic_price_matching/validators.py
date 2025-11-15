from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, MutableMapping, Optional, TypedDict

from django.core.exceptions import ValidationError

from automatic_price_matching.total_cost import TotalCostCalculator
from automatic_price_matching.normalization import canonicalize_job_code

# ---------------------------------------------------------------------------
# Regex patterns for identifying numeric formatting variants & disallowed
# expression-like inputs (we explicitly reject multiplication / equations so
# the service never evaluates user supplied expressions).
# ---------------------------------------------------------------------------
_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")
_MULTIPLICATION_PATTERN = re.compile(r"\d+\s*[xX]\s*\d+")
_ROW_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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


def _clean_job_code(
    errors: MutableMapping[str, List[str]],
    value: Any,
    field: str,
    *,
    required: bool = False,
) -> str:
    """Return a canonical job code while enforcing safe characters."""
    if value is None:
        if required:
            errors[field].append("This field cannot be null.")
        return ""
    if not isinstance(value, str):
        errors[field].append("Expected a string value.")
        return ""

    raw_text = value.strip()
    if required and not raw_text:
        errors[field].append("This field cannot be blank.")
        return ""
    if not raw_text:
        return ""

    upper_text = raw_text.upper()
    sanitized = re.sub(r"[^A-Za-z0-9.\-_/ ]", "", upper_text)
    if sanitized != upper_text:
        errors[field].append("Job code contains invalid characters.")
        return ""
    canonical = canonicalize_job_code(sanitized)
    if not canonical:
        errors[field].append("Job code must contain alphanumeric characters.")
        return ""
    if len(canonical) > 64:
        errors[field].append("Job code is too long (max 64 characters).")
        return ""
    return canonical


def _clean_row_key(
    errors: MutableMapping[str, List[str]],
    value: Any,
) -> Optional[str]:
    """Validate the optional row key used for session overrides."""
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        errors["row_key"].append("Row key must be a string.")
        return None

    candidate = value.strip()
    if not candidate:
        errors["row_key"].append("Row key cannot be blank.")
        return None
    if len(candidate) > 128:
        errors["row_key"].append("Row key is too long (max 128 characters).")
        return None
    if not _ROW_KEY_PATTERN.match(candidate):
        errors["row_key"].append("Row key contains invalid characters.")
        return None
    return candidate


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
    cleaned["code"] = _clean_job_code(errors, payload.get("code"), "code", required=True)
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


def validate_recompute_payload(payload: Any) -> Dict[str, Any]:
    """Validate payload submitted to ``recompute_total_cost`` endpoint."""
    if payload is None:
        raise ValidationError({"__all__": ["Payload cannot be null."]})
    if not isinstance(payload, dict):
        raise ValidationError({"__all__": ["Payload must be a JSON object."]})

    errors: Dict[str, List[str]] = defaultdict(list)
    cleaned: Dict[str, Any] = {}

    row_key_src = payload.get("row_key", payload.get("rowKey"))
    cleaned["row_key"] = _clean_row_key(errors, row_key_src)

    code_src = payload.get("code") or payload.get("kode")
    cleaned["code"] = _clean_job_code(errors, code_src, "code") if code_src not in (None, "") else ""

    analysis_src = payload.get("analysis_code") or payload.get("analysisCode")
    if analysis_src in (None, "") and cleaned["code"]:
        cleaned["analysis_code"] = cleaned["code"]
    else:
        cleaned["analysis_code"] = _clean_job_code(errors, analysis_src, "analysis_code") if analysis_src not in (None, "") else ""

    volume_src = payload.get("volume")
    if volume_src is None:
        volume_src = payload.get("qty", payload.get("quantity"))
    cleaned["volume"] = _coerce_decimal(errors, volume_src, "volume")
    unit_price_src = payload.get("unit_price", payload.get("unitPrice"))
    cleaned["unit_price"] = _coerce_decimal(errors, unit_price_src, "unit_price")

    if cleaned["volume"] is not None and cleaned["volume"] < 0:
        errors["volume"].append("Volume cannot be negative.")
    if cleaned["unit_price"] is not None and cleaned["unit_price"] < 0:
        errors["unit_price"].append("Unit price cannot be negative.")

    filtered_errors = {field: msgs for field, msgs in errors.items() if msgs}
    if filtered_errors:
        raise ValidationError(filtered_errors)
    return cleaned
