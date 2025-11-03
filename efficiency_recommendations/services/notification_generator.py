from typing import List, Dict


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
    print(f"\n{'='*60}")
    print(f"GENERATING NOTIFICATIONS")
    print(f"{'='*60}")

    if not items_with_status:
        print("No items to process. Returning empty list.")
        return []

    print(f"\nProcessing {len(items_with_status)} item(s)...")

    notifications = []

    for idx, item in enumerate(items_with_status, 1):
        item_name = item.get('name', 'Unknown Item')
        in_ahsp = item.get('in_ahsp', False)

        print(f"\n[{idx}/{len(items_with_status)}] {item_name}")
        print(f"   In AHSP: {in_ahsp}")

        # Only generate notification if item is NOT in AHSP
        if not in_ahsp:
            notification = {
                'type': 'NOT_IN_DATABASE',
                'item_name': item_name,
                'message': f"{item_name} tidak ditemukan di database AHSP dan tidak dapat diisi otomatis"
            }
            notifications.append(notification)
            print(f"   Action: Notification GENERATED")
        else:
            print(f"   Action: No notification needed (item found in AHSP)")

    print(f"\n{'='*60}")
    print(f"NOTIFICATION GENERATION COMPLETE")
    print(f"Total notifications: {len(notifications)}/{len(items_with_status)}")
    print(f"{'='*60}\n")

    return notifications
