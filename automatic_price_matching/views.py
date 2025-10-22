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
    for k, v in obj.items():
        if isinstance(v, Decimal):
            out[k] = format(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        else:
            out[k] = v
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
    volume_raw = payload.get("volume", payload.get("qty", payload.get("quantity", None)))

    volume = _safe_decimal(volume_raw) or Decimal("0")

    if not isinstance(code, str) or not code.strip():
        return JsonResponse({"error": "missing_code"}, status=400)

    logger.debug("recompute_total_cost called with payload=%s", payload)

    try:
        retriever = AhspPriceRetriever(CombinedAhspSource())
        unit_price = retriever.get_price_by_job_code(code)

        logger.debug("resolved unit_price for code=%s -> %s", code, unit_price)

        if unit_price is None:
            resp = {"unit_price": None, "total_cost": Decimal("0.00")}
            return JsonResponse(_serialize_decimals(resp), status=200)

        total = (unit_price * volume).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        resp = {
            "unit_price": unit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_cost": total,
        }
        return JsonResponse(_serialize_decimals(resp), status=200)
    except Exception as exc:
        logger.exception("recompute_total_cost failed")
        return JsonResponse({"error": "internal_error", "detail": str(exc)}, status=500)