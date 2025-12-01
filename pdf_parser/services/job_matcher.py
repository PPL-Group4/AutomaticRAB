import logging
from typing import Any, Dict
from automatic_job_matching.service.matching_service import MatchingService
from automatic_job_matching.models import UnmatchedAhsEntry

logger = logging.getLogger(__name__)

def _derive_status(match: Any) -> str:
    if isinstance(match, dict) and match:
        if match.get("confidence") == 1.0:
            return "found"
        return "similar"

    if isinstance(match, list):
        if len(match) == 1:
            return "similar"
        if len(match) > 1:
            return f"found {len(match)} similar"
    return "not found"

def match_description(description: str, unit: str = None) -> Dict[str, Any]:
    """Run automatic job matching for a single description."""
    if not description or not description.strip():
        return {"status": "skipped", "match": None}

    try:
        match = MatchingService.perform_best_match(description, unit=unit)  # ✅ Pass unit here
    except Exception as exc:
        logger.exception("Job matching failed for description")
        return {"status": "error", "match": None, "error": str(exc)}

    status = _derive_status(match)
    
    # Store unmatched entries in database
    if status == "not found":
        try:
            UnmatchedAhsEntry.objects.get_or_create(name=description)
            logger.info("Stored unmatched entry: %s", description[:50])
        except Exception as e:
            logger.error("Failed to store unmatched entry: %s", str(e))
    
    return {"status": status, "match": match}

