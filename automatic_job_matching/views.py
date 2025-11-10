from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view
import json
import logging

from automatic_job_matching.service.matching_service import MatchingService

logger = logging.getLogger(__name__)

@api_view(['POST'])
def match_best_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        logger.debug("match_best_view payload: %s", payload)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received in match_best_view")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = payload.get("description", "")
    unit = payload.get("unit", None)  # Extract unit from request

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

    if isinstance(result, dict) and "alternatives" in result:
        return JsonResponse(result, status=200)

    return JsonResponse({"status": status, "match": result}, status=200)

def job_matching_page(request):
    return render(request, "job_matching.html")