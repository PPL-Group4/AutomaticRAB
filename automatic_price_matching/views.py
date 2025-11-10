from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional

from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .price_retrieval import AhspPriceRetriever, CombinedAhspSource

logger = logging.getLogger(__name__)


def _serialize_decimals(obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in obj.items():
        if isinstance(value, Decimal):
            out[key] = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        else:
            out[key] = value
    return out


def _safe_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _store_override(request: HttpRequest, row_key: str, payload: Dict[str, Any]) -> None:
    overrides: Dict[str, Dict[str, Any]] = request.session.get("rab_overrides", {})
    overrides[row_key] = payload
    request.session["rab_overrides"] = overrides
    request.session.modified = True

def _parse_payload(request: HttpRequest) -> Optional[dict]:
    """Safely parse JSON body."""
    try:
        return json.loads(request.body.decode() or "{}")
    except Exception:
        return None


def _extract_fields(payload: dict) -> tuple[str, Optional[str], Any, Any, Optional[str]]:
    """Extract and normalize input fields from payload."""
    code = payload.get("code") or payload.get("kode") or ""
    row_key = payload.get("row_key") or payload.get("rowKey")
    volume_raw = payload.get("volume") or payload.get("qty") or payload.get("quantity")
    unit_price_raw = payload.get("unit_price") or payload.get("unitPrice")
    analysis_override = payload.get("analysis_code") or payload.get("analysisCode")
    return code, row_key, volume_raw, unit_price_raw, analysis_override


def _validate_numeric(volume_raw: Any, unit_price_raw: Any) -> Optional[tuple[Decimal, Optional[Decimal]]]:
    """Validate and convert numeric inputs."""
    volume = _safe_decimal(volume_raw)
    unit_price = _safe_decimal(unit_price_raw)

    # Reject invalid numeric input early
    if (
        (volume_raw not in (None, "", 0) and volume is None)
        or (unit_price_raw not in (None, "", 0) and unit_price is None)
    ):
        return None

    return volume or Decimal("0"), unit_price


def _get_unit_price(code: str, unit_price: Optional[Decimal]) -> Optional[Decimal]:
    """Fetch unit price if missing."""
    if unit_price is None and isinstance(code, str) and code.strip():
        retriever = AhspPriceRetriever(CombinedAhspSource())
        unit_price = retriever.get_price_by_job_code(code)
        logger.debug("resolved unit_price for code=%s -> %s", code, unit_price)
    return unit_price

@csrf_exempt
@require_POST
def recompute_total_cost(request: HttpRequest):
    """
    POST JSON: { "code": "A.1.1.4", "volume": 2.5 }
    Response JSON: { "unit_price": "1000.00", "total_cost": "2500.00" }
    """

    payload = _parse_payload(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    code, row_key, volume_raw, unit_price_raw, analysis_override = _extract_fields(payload)

    validated = _validate_numeric(volume_raw, unit_price_raw)
    if validated is None:
        return JsonResponse({"error": "Invalid numeric input"}, status=400)

    volume, unit_price = validated
    logger.debug("recompute_total_cost called with payload=%s", payload)

    try:
        unit_price = _get_unit_price(code, unit_price)
        total = (unit_price * volume).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if unit_price else Decimal("0.00")

        resp = {
            "unit_price": unit_price if unit_price is not None else None,
            "total_cost": total,
            "row_key": row_key,
        }

        if row_key:
            stored_payload: Dict[str, Any] = {
                "unit_price": resp["unit_price"],
                "total_price": resp["total_cost"],
                "volume": volume,
                "analysis_code": analysis_override or code,
            }
            _store_override(request, row_key, _serialize_decimals(stored_payload))

        return JsonResponse(_serialize_decimals(resp), status=200)

    except Exception as exc:
        logger.exception("recompute_total_cost failed")
        return JsonResponse({"error": "internal_error", "detail": str(exc)}, status=500)
