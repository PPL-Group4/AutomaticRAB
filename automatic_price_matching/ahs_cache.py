import logging
from typing import Dict, List
from automatic_job_matching.service.exact_matcher import AhsRow

logger = logging.getLogger(__name__)

class AhsCache:
    """Simple in-memory cache for AHSP lookups to reduce repeated DB queries."""

    def __init__(self):
        # Key-value store for different lookup types
        self._cache_by_code: Dict[str, List[AhsRow]] = {}
        self._cache_by_name: Dict[str, List[AhsRow]] = {}
        self._all_ahs: List[AhsRow] | None = None

    def get_by_code(self, code: str) -> List[AhsRow] | None:
        return self._cache_by_code.get(code)

    def set_by_code(self, code: str, rows: List[AhsRow]) -> None:
        logger.debug("Caching %d AHSP rows for code=%s", len(rows), code)
        self._cache_by_code[code] = rows

    def get_by_name(self, token: str) -> List[AhsRow] | None:
        return self._cache_by_name.get(token)

    def set_by_name(self, token: str, rows: List[AhsRow]) -> None:
        logger.debug("Caching %d AHSP rows for name token=%s", len(rows), token)
        self._cache_by_name[token] = rows

    def get_all(self) -> List[AhsRow] | None:
        return self._all_ahs

    def set_all(self, rows: List[AhsRow]) -> None:
        logger.debug("Caching full AHSP list with %d entries", len(rows))
        self._all_ahs = rows
