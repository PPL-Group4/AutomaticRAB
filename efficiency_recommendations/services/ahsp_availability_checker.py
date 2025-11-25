from typing import List, Dict
import logging
from functools import lru_cache
from automatic_job_matching.service.matching_service import MatchingService

logger = logging.getLogger(__name__)

# Cache for matching results to avoid redundant lookups
@lru_cache(maxsize=1024)
def _check_item_in_ahsp_cached(item_name: str) -> bool:
    """Cached version of AHSP check for a single item name."""
    try:
        match = MatchingService.perform_best_match(item_name)
        # Check if match was found
        if match is None or (isinstance(match, list) and len(match) == 0):
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking AHSP for item '{item_name}': {e}")
        return False


def check_items_in_ahsp(items: List[Dict]) -> List[Dict]:
    """
    Check if items exist in AHSP database.

    Args:
        items: List of items with structure:
            [
                {
                    'name': str,
                    'cost': Decimal,
                    'weight_pct': Decimal,
                    'quantity': Decimal,
                    'unit_price': Decimal
                }
            ]

    Returns:
        List of items with AHSP availability status:
            [
                {
                    'name': str,
                    'cost': Decimal,
                    'weight_pct': Decimal,
                    'quantity': Decimal,
                    'unit_price': Decimal,
                    'in_ahsp': bool,  # True if found in AHSP, False otherwise
                }
            ]
    """
    if not items:
        return []

    result = []
    for item in items:
        item_result = item.copy()
        item_result['in_ahsp'] = _check_item_in_ahsp_cached(item['name'])
        result.append(item_result)

    return result