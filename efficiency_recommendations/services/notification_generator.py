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

    # Generate notifications only for items NOT in AHSP
    notifications = [
        {
            'type': 'NOT_IN_DATABASE',
            'item_name': item.get('name', 'Unknown Item'),
            'message': f"{item.get('name', 'Unknown Item')} tidak ditemukan di database AHSP dan tidak dapat diisi otomatis"
        }
        for item in items_with_status
        if not item.get('in_ahsp', False)
    ]

    # Apply duplicate prevention using the dedicated service
    return DuplicatePreventionService.remove_duplicates(notifications)
