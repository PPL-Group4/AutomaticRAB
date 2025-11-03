from typing import Dict


def identify_highest_cost_weight_item(job_data: Dict) -> Dict:
    items = job_data.get('items', [])
    
    if not items:
        return {
            'job_id': job_data['job_id'],
            'job_name': job_data['job_name'],
            'total_cost': job_data['total_cost'],
            'highest_item': None,
        }
    
    # Find the item with maximum weight percentage
    highest_item = max(items, key=lambda x: x['weight_pct'])
    
    return {
        'job_id': job_data['job_id'],
        'job_name': job_data['job_name'],
        'total_cost': job_data['total_cost'],
        'highest_item': highest_item,
    }
