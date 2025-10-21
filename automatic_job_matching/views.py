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
    result = MatchingService.perform_best_match(description)

    if isinstance(result, dict) and result:
        status = "found"
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
def suggest_matches_view(request):
    query = request.GET.get("q", "").strip()
    description = request.GET.get("description", "").strip()
    limit_param = request.GET.get("limit", "10")

    try:
        limit = max(1, min(int(limit_param), 25))
    except (TypeError, ValueError):
        limit = 10

    suggestions = []

    try:
        if query:
            suggestions = MatchingService.search_candidates(query, limit)
        elif description:
            try:
                candidates = MatchingService.perform_multiple_match(description, limit, 0.4)
            except TypeError:
                candidates = MatchingService.perform_multiple_match(description, limit)
            suggestions = candidates if isinstance(candidates, list) else []
    except Exception:
        logger.exception("Failed to generate match suggestions", extra={"query": query, "description": description})
        suggestions = []

    payload = [
        {
            "code": item.get("code", ""),
            "name": item.get("name", ""),
            "confidence": item.get("confidence"),
        }
        for item in suggestions
        if item and item.get("code")
    ][:limit]

    return JsonResponse({"results": payload})
