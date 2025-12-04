from typing import List, Dict
from .duplicate_prevention_service import DuplicatePreventionService


def generate_notifications(items_with_status: List[Dict]) -> List[Dict]:
    """
    Generate notifications for items that are NOT found in AHSP database.

    Args:
        items_with_status: List of items with AHSP availability status:
            [
                {
                    'name': str,
                    'cost': Decimal,
                    'weight_pct': Decimal,
                    'in_ahsp': bool
                }
            ]

    Returns:
        List of notifications for items not in AHSP:
            [
                {
                    'type': 'NOT_IN_DATABASE',
                    'item_name': str,
                    'message': str
                }
            ]
    """
    if not items_with_status:
        return []

    notifications = []

    for item in items_with_status:
        item_name = item.get('name', 'Unknown Item')
        in_ahsp = item.get('in_ahsp', False)

        # Only generate notification if item is NOT in AHSP
        if not in_ahsp:
            notification = {
                'type': 'NOT_IN_DATABASE',
                'item_name': item_name,
                'message': "{} tidak ditemukan di database AHSP dan tidak dapat diisi otomatis".format(item_name)
            }
            notifications.append(notification)

    # Apply duplicate prevention using the dedicated service
    unique_notifications = DuplicatePreventionService.remove_duplicates(notifications)

    return unique_notifications
