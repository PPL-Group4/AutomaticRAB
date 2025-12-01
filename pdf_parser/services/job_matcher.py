import logging
import re
from typing import Any, Dict
from automatic_job_matching.service.matching_service import MatchingService

logger = logging.getLogger(__name__)

_CONTROL_CHARS = ''.join(chr(i) for i in range(0, 32)) + chr(127)
_CONTROL_CHAR_PATTERN = re.compile(f"[{re.escape(_CONTROL_CHARS)}]")
_MAX_DESCRIPTION_LENGTH = 1024

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

def _sanitize_description(description: Any) -> str:
    if description is None:
        return ""

    if not isinstance(description, str):
        description = str(description)

    sanitized = _CONTROL_CHAR_PATTERN.sub(" ", description)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if len(sanitized) > _MAX_DESCRIPTION_LENGTH:
        sanitized = sanitized[:_MAX_DESCRIPTION_LENGTH]
    return sanitized

def match_description(description: str, unit: str = None) -> Dict[str, Any]:
    """Run automatic job matching for a single description."""
    sanitized_description = _sanitize_description(description)
    if not sanitized_description:
        return {"status": "skipped", "match": None}

    try:
        match = MatchingService.perform_best_match(sanitized_description, unit=unit)
    except Exception as exc:
        logger.exception("Job matching failed for description")
        return {
            "status": "error",
            "match": None,
            "error": "Job matching failed; please try again later.",
        }

    return {"status": _derive_status(match), "match": match}

