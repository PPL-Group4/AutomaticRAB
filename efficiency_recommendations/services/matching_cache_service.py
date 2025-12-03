"""
Request-level caching service for job matching results.

This service provides in-memory caching of matching results during a single request,
preventing redundant matching calls for the same items.
"""
from typing import Dict, Any, Optional
from automatic_job_matching.service.matching_service import MatchingService


class MatchingCacheService:
    """
    Thread-safe request-level cache for job matching results.

    Usage:
        cache = MatchingCacheService()
        result = cache.get_or_match("item description")
    """

    def __init__(self):
        """Initialize empty cache."""
        self._cache: Dict[str, Any] = {}
        self._stats = {"hits": 0, "misses": 0}

    def get_or_match(self, item_name: str) -> Optional[Any]:
        """
        Get cached match result or perform matching if not cached.

        Args:
            item_name: Item description to match

        Returns:
            Matching result from MatchingService or cache
        """
        if not item_name or not item_name.strip():
            return None

        # Normalize key for consistent caching
        cache_key = item_name.strip().lower()

        # Check cache first
        if cache_key in self._cache:
            self._stats["hits"] += 1
            return self._cache[cache_key]

        # Cache miss - perform matching
        self._stats["misses"] += 1
        result = MatchingService.perform_best_match(item_name)

        # Store in cache
        self._cache[cache_key] = result

        return result

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()

    def clear(self):
        """Clear the cache."""
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0}


def extract_ahsp_data_from_match(match_result: Any, item_name: str = "") -> Dict[str, Any]:
    """
    Extract AHSP data from matching result.

    Args:
        match_result: Result from MatchingService
        item_name: Item name (for status determination)

    Returns:
        Dict with: ahsp_code, ahsp_unit_price, in_ahsp, reference_price
    """
    from decimal import Decimal

    ahsp_data = {
        "ahsp_code": None,
        "ahsp_unit_price": None,
        "in_ahsp": False,
        "reference_price": None
    }

    if not match_result:
        return ahsp_data

    # Mark as found in AHSP
    ahsp_data["in_ahsp"] = True

    # Extract from dict result
    if isinstance(match_result, dict):
        ahsp_data["ahsp_code"] = match_result.get("code")

        # Extract unit price
        unit_price = match_result.get("unit_price") or match_result.get("price")
        if unit_price is not None:
            try:
                price_decimal = Decimal(str(unit_price))
                ahsp_data["ahsp_unit_price"] = price_decimal
                ahsp_data["reference_price"] = price_decimal
            except (ValueError, TypeError):
                pass

    # Extract from list result (take first match)
    elif isinstance(match_result, list) and len(match_result) > 0:
        first_match = match_result[0]
        if isinstance(first_match, dict):
            ahsp_data["ahsp_code"] = first_match.get("code")

            unit_price = first_match.get("unit_price") or first_match.get("price")
            if unit_price is not None:
                try:
                    price_decimal = Decimal(str(unit_price))
                    ahsp_data["ahsp_unit_price"] = price_decimal
                    ahsp_data["reference_price"] = price_decimal
                except (ValueError, TypeError):
                    pass

    return ahsp_data
