from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher

@csrf_exempt
@require_POST
def match_exact_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    description = payload.get("description", "")
    matcher = ExactMatcher(DbAhsRepository())
    result = matcher.match(description)

    return JsonResponse({"match": result}, status=200)