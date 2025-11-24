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

    status = MatchingService.determine_status(result)

    if status == "not found":
        log_unmatched_entry(description, unit)

    if isinstance(result, dict) and "alternatives" in result:
        return JsonResponse(result, status=200)

    return JsonResponse({"status": status, "match": result}, status=200)


@api_view(['POST'])
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
def match_bulk_view(request):
    if request.content_type and "application/json" not in request.content_type:
        security_logger.warning("Rejected bulk request with invalid content type: %s", request.content_type)
        return JsonResponse({"error": "Unsupported content type"}, status=415)

    try:
        ensure_payload_size(request.body)
    except SecurityValidationError as exc:
        security_logger.warning("Bulk payload rejected due to size: %s", exc)
        return JsonResponse({"error": "Payload too large"}, status=413)

    try:
        payload = json.loads(request.body.decode("utf-8") or "[]")
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received in match_bulk_view")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(payload, list):
        logger.warning("Bulk match payload is not an array")
        return JsonResponse({"error": "Payload must be a list"}, status=400)

    total_items = len(payload)
    results = [None] * total_items
    valid_entries = []
    valid_indices = []

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            results[idx] = {
                "index": idx,
                "status": "error",
                "error": "Each item must be an object.",
                "match": None,
            }
            continue

        try:
            description = sanitize_description(item.get("description"))
            unit = sanitize_unit(item.get("unit"))
        except (SecurityValidationError, ValidationError) as exc:
            security_logger.warning("Rejected bulk item at index %d: %s", idx, exc)
            results[idx] = {
                "index": idx,
                "status": "error",
                "error": "Invalid input",
                "match": None,
            }
            continue

        tag_match_event(description, unit)
        valid_entries.append({"description": description, "unit": unit})
        valid_indices.append(idx)

    if valid_entries:
        bulk_results = MatchingService.perform_bulk_best_match(valid_entries)

        for original_index, bulk_result in zip(valid_indices, bulk_results):
            results[original_index] = {"index": original_index, **bulk_result}

            if bulk_result.get("status") == "not found":
                log_unmatched_entry(bulk_result.get("description"), bulk_result.get("unit"))

    for idx, entry in enumerate(results):
        if entry is None:
            results[idx] = {
                "index": idx,
                "status": "error",
                "error": "Internal error",
                "match": None,
            }

    logger.info("match_bulk_view processed %d items", total_items)
    return JsonResponse({"results": results}, status=200)

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