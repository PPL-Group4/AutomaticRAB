from decimal import Decimal
from typing import Dict


def identify_highest_cost_weight_item(job_data: Dict) -> Dict:
    items = job_data.get('items', [])
    total_cost = Decimal(str(job_data.get('total_cost', '0') or '0'))

    # ✅ If no items or total_cost == 0 → skip
    if not items or total_cost == 0:
        return {
            'job_id': job_data['job_id'],
            'job_name': job_data['job_name'],
            'total_cost': total_cost,
            'highest_item': None,
        }

    highest_item = max(items, key=lambda x: x['weight_pct'])
    return {
        'job_id': job_data['job_id'],
        'job_name': job_data['job_name'],
        'total_cost': total_cost,
        'highest_item': highest_item,
    }
