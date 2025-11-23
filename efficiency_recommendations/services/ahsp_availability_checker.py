from typing import List, Dict
import logging
from automatic_job_matching.service.matching_service import MatchingService

logger = logging.getLogger(__name__)


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
    print("\n" + "="*60)
    print("CHECKING ITEMS IN AHSP DATABASE")
    print("="*60)

    if not items:
        print("No items to check. Returning empty list.")
        return []

    print("\nChecking {} item(s) against AHSP database...".format(len(items)))

    result = []

    for idx, item in enumerate(items, 1):
        print("\n[{}/{}] Checking item: {}".format(idx, len(items), item['name']))

        # Create a copy of the item to avoid mutating the original
        item_result = item.copy()

        try:
            # Try to find the item in AHSP database
            print("   Calling MatchingService.perform_best_match...")
            match = MatchingService.perform_best_match(item['name'])

            print("   Match result type: {}".format(type(match)))
            print("   Match result: {}".format(match))

            # Check if match was found
            # Match can be None, empty list [], or a dict/list with results
            if match is None or (isinstance(match, list) and len(match) == 0):
                item_result['in_ahsp'] = False
                print("   Result: NOT FOUND in AHSP")
            else:
                item_result['in_ahsp'] = True
                print("   Result: FOUND in AHSP")

        except Exception as e:
            # If matching service fails, mark as not found
            logger.error("Error checking AHSP for item '{}': {}".format(item['name'], str(e)))
            print("   ERROR: {}".format(str(e)))
            print("   Result: NOT FOUND (due to error)")
            item_result['in_ahsp'] = False

        result.append(item_result)

    print("\n" + "="*60)
    print("AHSP CHECK COMPLETE")
    print("Found in AHSP: {}/{}".format(sum(1 for r in result if r['in_ahsp']), len(result)))
    print("="*60 + "\n")

    return result