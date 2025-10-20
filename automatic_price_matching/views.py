import json
import logging
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError

from .service import AutomaticPriceMatchingService
from .price_retrieval import AhspPriceRetriever, MockAhspSource
from .total_cost import TotalCostCalculator

logger = logging.getLogger(__name__)


def _serialize_decimals(obj: dict) -> dict:
    """Convert Decimal values for JSON serialization (in-place shallow)."""
    out = {}
    for k, v in obj.items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def _safe_decimal(value):
    """Try to coerce common inputs to Decimal; return None on failure/blank."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _validation_only_missing_required(exc: ValidationError) -> bool:
    """Return True if ValidationError appears to only contain 'required' / missing-field errors."""
    msg_dict = getattr(exc, "message_dict", None)
    if isinstance(msg_dict, dict):
        for v in msg_dict.values():
            items = v if isinstance(v, (list, tuple)) else [v]
            for item in items:
                text = str(item).lower()
                # allow messages that indicate missing/required only
                if "required" in text or "missing" in text or "cannot be blank" in text:
                    continue
                # any other message (format, numeric, invalid, etc.) -> not eligible for lenient fallback
                return False
        return True
    # Fallback: if message text contains only 'required' / 'missing' hints
    text = str(exc).lower()
    if not text:
        return False
    # if any non-missing hint present, consider it fatal
    for forbidden in ("must be", "invalid", "numeric", "cannot be", "must not", "expression"):
        if forbidden in text:
            return False
    return "required" in text or "missing" in text


@csrf_exempt
@require_POST
def recompute_total_cost(request):
    """Compute total cost / AHSP match for a single payload using service layer.

    Backwards-compatible: when no AHSP identifiers (code/name) are present use the
    legacy lenient computation path (coerce volume/unit_price). Otherwise use
    the strict service flow and only fall back for missing-field validation errors.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Legacy fast-path: if caller didn't send AHSP identifiers use lenient behaviour
    if not data.get("code") and not data.get("name"):
        vol = _safe_decimal(data.get("volume"))
        unit = _safe_decimal(data.get("unit_price"))

        # If both values are missing/unparsable -> treat as invalid input
        if vol is None and unit is None:
            return JsonResponse({"error": "Invalid payload"}, status=400)

        # Legacy rule: if unit_price missing/unparsable -> total 0, else use calculator
        if unit is None:
            total = Decimal("0")
        else:
            total = TotalCostCalculator.calculate(vol, unit)
            if total is None:
                total = Decimal("0")

        fallback_result = {
            "uraian": data.get("name"),
            "unit_price": unit,
            "total_cost": total,
            "match_status": "Needs Manual Input" if unit is None else "Provided",
            "is_editable": True,
        }
        return JsonResponse(_serialize_decimals(fallback_result), status=200)

    svc = AutomaticPriceMatchingService(
        price_retriever=AhspPriceRetriever(MockAhspSource({}))
    )

    try:
        result = svc.match_one(data)
    except ValidationError as exc:
        # Only fallback when validation indicates missing/required fields.
        if not _validation_only_missing_required(exc):
            logger.debug("recompute_total_cost validation error (fatal): %s", exc)
            return JsonResponse(
                {"error": "Invalid payload", "details": getattr(exc, "message_dict", str(exc))},
                status=400,
            )

        # Fall back to legacy lenient behaviour for missing-field errors:
        logger.debug("recompute_total_cost validation missing fields, falling back: %s", exc)
        vol = _safe_decimal(data.get("volume"))
        unit = _safe_decimal(data.get("unit_price"))

        # Legacy rule: if unit_price missing or unparsable -> total 0, else use calculator
        if unit is None:
            total = Decimal("0")
        else:
            total = TotalCostCalculator.calculate(vol, unit)
            if total is None:
                total = Decimal("0")

        fallback_result = {
            "uraian": data.get("name"),
            "unit_price": unit,
            "total_cost": total,
            "match_status": "Needs Manual Input" if unit is None else "Provided",
            "is_editable": True,
        }
        return JsonResponse(_serialize_decimals(fallback_result), status=200)
    except Exception:
        logger.exception("Unexpected error in recompute_total_cost")
        return JsonResponse({"error": "Server error"}, status=500)

    # Convert Decimal fields to strings for JSON
    serializable = _serialize_decimals(result)
    return JsonResponse(serializable)