from django.http import JsonResponse
from rest_framework.decorators import api_view
import json
import logging

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer

logger = logging.getLogger(__name__)

class MatchingService:
    @staticmethod
    def perform_exact_match(description):
        matcher = ExactMatcher(DbAhsRepository())
        return matcher.match(description)

    @staticmethod
    def perform_fuzzy_match(description, min_similarity=0.6):
        logger.info("perform_fuzzy_match called (len=%d, min_similarity=%.2f)",
                    len(description), min_similarity)
        
        matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
        confidence_result = getattr(matcher, 'match_with_confidence', None)
        if callable(confidence_result):
            result = confidence_result(description)
        else:
            result = matcher.match(description)

        logger.debug("Fuzzy match result: %s", result)
        return result
    
    @staticmethod
    def perform_multiple_match(description, limit=5, min_similarity=0.6):
        logger.info("perform_multiple_match called (len=%d, limit=%d, min_similarity=%.2f)",
                    len(description), limit, min_similarity)
        
        matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
        confidence_multi = getattr(matcher, 'find_multiple_matches_with_confidence', None)
        
        if callable(confidence_multi):
            results = confidence_multi(description, limit)
        else:
            results = matcher.find_multiple_matches(description, limit)
            
        logger.debug("Multiple fuzzy match results count=%d", len(results))
        return results
    

@api_view(['POST'])
def match_exact_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = payload.get("description", "")

    result = MatchingService.perform_exact_match(description)

    return JsonResponse({"match": result}, status=200)

@api_view(['POST'])
def match_fuzzy_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        logger.debug("match_fuzzy_view payload: %s", payload)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received in match_fuzzy_view")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = payload.get("description", "")
    min_similarity = payload.get("min_similarity", 0.6)

    result = MatchingService.perform_fuzzy_match(description, min_similarity)

    return JsonResponse({"match": result}, status=200)

@api_view(['POST'])
def match_multiple_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        logger.debug("match_multiple_view payload: %s", payload)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received in match_multiple_view")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = payload.get("description", "")
    limit = payload.get("limit", 5)
    min_similarity = payload.get("min_similarity", 0.6)

    results = MatchingService.perform_multiple_match(description, limit, min_similarity)

    return JsonResponse({"matches": results}, status=200)

@api_view(['POST'])
def debug_ahs_data(request):
    try:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            logger.debug("debug_ahs_data payload: %s", payload)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received in debug_ahs_data")
            payload = {}

        search_term = payload.get('search', 'mengangkut')
        limit = payload.get('limit', 50)  # Allow customizable limit

        from rencanakan_core.models import Ahs

        filtered_records = Ahs.objects.filter(name__icontains=search_term)

        all_records = Ahs.objects.all()[:10]

        filtered_data = [{"id": ahs.id, "code": ahs.code, "name": ahs.name} for ahs in filtered_records[:limit]]
        all_data = [{"id": ahs.id, "code": ahs.code, "name": ahs.name} for ahs in all_records]
        
        logger.info("debug_ahs_data returning %d filtered / %d total records",
                    len(filtered_data), Ahs.objects.count())
        
        return JsonResponse({
            "search_term": search_term,
            "requested_limit": limit,
            "total_count": Ahs.objects.count(),
            "filtered_count": filtered_records.count(),
            "returned_count": len(filtered_data),
            "filtered_samples": filtered_data,
            "all_samples": all_data
        })
    except Exception as e:
        logger.exception("Unexpected error in debug_ahs_data: %s", e)
        return JsonResponse({"error": str(e)})
