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


@csrf_exempt
@require_POST
def recompute_total_cost(request: HttpRequest):
    """
    POST JSON: { "code": "A.1.1.4", "volume": 2.5 }
    Response JSON: { "unit_price": "1000.00", "total_cost": "2500.00" }
    """
    try:
        payload = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    code = payload.get("code") or payload.get("kode") or ""
    row_key = payload.get("row_key") or payload.get("rowKey")
    volume_raw = payload.get("volume", payload.get("qty", payload.get("quantity", None)))
    unit_price_raw = payload.get("unit_price", payload.get("unitPrice"))
    analysis_override = payload.get("analysis_code") or payload.get("analysisCode")

    volume = _safe_decimal(volume_raw) or Decimal("0")
    unit_price = _safe_decimal(unit_price_raw)
    # Reject invalid numeric input early
    if (volume_raw not in (None, "", 0) and _safe_decimal(volume_raw) is None) or (
            unit_price_raw not in (None, "", 0) and _safe_decimal(unit_price_raw) is None
    ):
        return JsonResponse({"error": "Invalid numeric input"}, status=400)

    logger.debug("recompute_total_cost called with payload=%s", payload)

    try:
        if unit_price is None and isinstance(code, str) and code.strip():
            retriever = AhspPriceRetriever(CombinedAhspSource())
            unit_price = retriever.get_price_by_job_code(code)
            logger.debug("resolved unit_price for code=%s -> %s", code, unit_price)

        if unit_price is None:
            total = Decimal("0.00")
        else:
            total = (unit_price * volume).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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