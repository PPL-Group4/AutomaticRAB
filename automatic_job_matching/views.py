from django.http import JsonResponse
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

    return JsonResponse({"match": result}, status=200)