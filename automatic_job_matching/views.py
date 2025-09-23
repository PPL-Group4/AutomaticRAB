from django.http import JsonResponse
from rest_framework.decorators import api_view
import json

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher

@api_view(['POST'])
def match_exact_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    description = payload.get("description", "")
    
    result = MatchingService.perform_exact_match(description)

    return JsonResponse({"match": result}, status=200)

class MatchingService:
    
    @staticmethod
    def perform_exact_match(description):
        matcher = ExactMatcher(DbAhsRepository())
        return matcher.match(description)
