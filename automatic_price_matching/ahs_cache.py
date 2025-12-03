import logging
from typing import Dict, List
from automatic_job_matching.service.exact_matcher import AhsRow

logger = logging.getLogger(__name__)

class AhsCache:
    """Simple in-memory cache for AHSP lookups to reduce repeated DB queries.

    Uses class-level (singleton) cache to share data across all instances.
    This is critical when multiple repository instances are created during
    parsing/matching operations - they all share the same cached AHSP data.
    """

    # Class-level shared cache (singleton pattern)
    _shared_cache_by_code: Dict[str, List[AhsRow]] = {}
    _shared_cache_by_name: Dict[str, List[AhsRow]] = {}
    _shared_all_ahs: List[AhsRow] | None = None

    def __init__(self):
        # Instance just uses the shared class-level cache
        pass

    def get_by_code(self, code: str) -> List[AhsRow] | None:
        return self._shared_cache_by_code.get(code)

    def set_by_code(self, code: str, rows: List[AhsRow]) -> None:
        logger.debug("Caching %d AHSP rows for code=%s", len(rows), code)
        self._shared_cache_by_code[code] = rows

    def get_by_name(self, token: str) -> List[AhsRow] | None:
        return self._shared_cache_by_name.get(token)

    def set_by_name(self, token: str, rows: List[AhsRow]) -> None:
        logger.debug("Caching %d AHSP rows for name token=%s", len(rows), token)
        self._shared_cache_by_name[token] = rows

    def get_all(self) -> List[AhsRow] | None:
        return self._shared_all_ahs

    def set_all(self, rows: List[AhsRow]) -> None:
        logger.debug("Caching full AHSP list with %d entries", len(rows))
        AhsCache._shared_all_ahs = rows

    @classmethod
    def clear_all(cls) -> None:
        """Clear all caches (useful for testing)."""
        cls._shared_cache_by_code.clear()
        cls._shared_cache_by_name.clear()
        cls._shared_all_ahs = None
        logger.info("Cleared all AHSP caches")

