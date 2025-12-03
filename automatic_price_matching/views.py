from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

import sentry_sdk
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .price_retrieval import AhspPriceRetriever, CombinedAhspSource
from .validators import validate_recompute_payload

logger = logging.getLogger(__name__)


def _serialize_decimals(obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in obj.items():
        if isinstance(value, Decimal):
            out[key] = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        else:
            out[key] = value
    return out


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
    with sentry_sdk.configure_scope() as scope:
        scope.set_context("request_info", {
            "content_type": request.content_type,
            "method": request.method,
        })

    if request.content_type and "application/json" not in request.content_type:
        sentry_sdk.capture_message("Unsupported media type", level="warning")
        return JsonResponse({"error": "unsupported_media_type"}, status=415)

    try:
        payload = json.loads(request.body.decode() or "{}")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({"error": "invalid_json"}, status=400)

    try:
        cleaned_payload = validate_recompute_payload(payload)
    except ValidationError as exc:
        sentry_sdk.set_context("validation_error", {
            "payload": payload,
            "errors": exc.message_dict
        })
        sentry_sdk.capture_message("Validation failed for recompute request", level="warning")
        return JsonResponse({"error": "invalid_input", "detail": exc.message_dict}, status=400)

    canonical_code = cleaned_payload.get("analysis_code") or cleaned_payload.get("code")
    row_key = cleaned_payload.get("row_key")
    volume_value = cleaned_payload.get("volume")
    unit_price = cleaned_payload.get("unit_price")
    volume = volume_value if volume_value is not None else Decimal("0")
    analysis_code_value = cleaned_payload.get("analysis_code") or cleaned_payload.get("code") or ""

    logger.debug("recompute_total_cost called with payload=%s", payload)

    sentry_sdk.set_context("price_calculation", {
        "canonical_code": canonical_code,
        "row_key": row_key,
        "volume": str(volume),
        "initial_unit_price": str(unit_price) if unit_price else None,
    })

    try:
        if unit_price is None and isinstance(canonical_code, str) and canonical_code.strip():
            retriever = AhspPriceRetriever(CombinedAhspSource())
            unit_price = retriever.get_price_by_job_code(canonical_code)
            logger.debug("resolved unit_price for code=%s -> %s", canonical_code, unit_price)

            if unit_price is None:
                sentry_sdk.capture_message(
                    f"Price not found for code: {canonical_code}",
                    level="info"
                )

        if unit_price is None:
            total = Decimal("0.00")
        else:
            total = (unit_price * volume).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        resp = {
            "unit_price": unit_price if unit_price is not None else None,
            "total_cost": total,
            "row_key": row_key,
        }
        from automatic_price_matching.monitoring import record_price_override

        # After retrieving or reading user-provided unit_price
        if unit_price is not None:
            retriever = AhspPriceRetriever(CombinedAhspSource())
            known_price = retriever.get_price_by_job_code(canonical_code)

            if known_price is not None and Decimal(unit_price) != known_price:
                record_price_override(canonical_code, known_price, unit_price)

        if row_key:
            stored_payload: Dict[str, Any] = {
                "unit_price": resp["unit_price"],
                "total_price": resp["total_cost"],
                "volume": volume,
                "analysis_code": analysis_code_value,
            }
            _store_override(request, row_key, _serialize_decimals(stored_payload))

        return JsonResponse(_serialize_decimals(resp), status=200)
    except Exception as exc:
        logger.exception("recompute_total_cost failed")
        sentry_sdk.capture_exception(exc)
        return JsonResponse({"error": "internal_error", "detail": str(exc)}, status=500)
