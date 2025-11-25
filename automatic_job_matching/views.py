from django.core.exceptions import ValidationError
import json
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from rest_framework.decorators import api_view

from automatic_job_matching.service.ahs_breakdown_service import get_ahs_breakdown
from automatic_job_matching.service.matching_service import MatchingService
from automatic_job_matching.utils.monitoring import tag_match_event, log_unmatched_entry
from automatic_job_matching.security import (
    SecurityValidationError,
    ensure_payload_size,
    sanitize_description,
    sanitize_unit,
)

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security.audit")

@api_view(['POST'])
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
def match_best_view(request):
    if request.content_type and "application/json" not in request.content_type:
        security_logger.warning("Rejected request with invalid content type: %s", request.content_type)
        return JsonResponse({"error": "Unsupported content type"}, status=415)

    try:
        ensure_payload_size(request.body)
    except SecurityValidationError as exc:
        security_logger.warning("Payload rejected due to size: %s", exc)
        return JsonResponse({"error": "Payload too large"}, status=413)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        logger.debug("match_best_view payload keys: %s", list(payload.keys()))
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received in match_best_view")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        description = sanitize_description(payload.get("description"))
        unit = sanitize_unit(payload.get("unit"))
    except (SecurityValidationError, ValidationError) as exc:
        security_logger.warning("Rejected payload on validation error: %s", exc)
        return JsonResponse({"error": "Invalid input"}, status=400)

    tag_match_event(description, unit)
    result = MatchingService.perform_best_match(description, unit=unit)  # Pass unit to matching service

    if isinstance(result, dict) and result:
        if result.get("confidence", 1.0) == 1.0:
            status = "found"
        else:
            status = "similar"
    elif isinstance(result, list) and len(result) == 1:
        status = "similar"
    elif isinstance(result, list) and len(result) > 1:
        status = f"found {len(result)} similar"
    else:
        status = "not found"

    return JsonResponse({"status": status, "match": result}, status=200)

def job_matching_page(request):
    return render(request, "job_matching.html")


@api_view(['GET'])
def ahs_breakdown_view(request, code: str):
    logger.debug("ahs_breakdown_view called for code=%s", code)
    breakdown = get_ahs_breakdown(code)

    if not breakdown:
        logger.info("Breakdown not found for code=%s", code)
        return JsonResponse({"error": "AHS code not found"}, status=404)

    return JsonResponse({
        "code": code,
        "breakdown": breakdown,
    }, status=200)