from typing import Dict, List

# Constants
COST_FORMAT = "      Cost: Rp {:,} ({}%)"


def identify_top_cost_contributors(job_data: Dict, top_n: int = 3) -> Dict:
    """
    Identify the top N cost contributors from a job's items.

    Args:
        job_data: Dictionary containing job information with structure:
            {
                'job_id': int,
                'job_name': str,
                'total_cost': Decimal,
                'items': List[Dict] - list of items with 'weight_pct' field
            }
        top_n: Number of top items to return (default: 3)

    Returns:
        Dictionary with structure:
            {
                'job_id': int,
                'job_name': str,
                'total_cost': Decimal,
                'top_items': List[Dict] - top N items sorted by weight_pct descending
            }
    """
    print("\n" + "="*60)
    print("IDENTIFYING TOP {} COST CONTRIBUTORS".format(top_n))
    print("="*60)

    # Extract job metadata
    job_id = job_data['job_id']
    job_name = job_data['job_name']
    total_cost = job_data['total_cost']
    items = job_data['items']

    print("\nJob Information:")
    print("   Job ID: {}".format(job_id))
    print("   Job Name: {}".format(job_name))
    print("   Total Cost: Rp {:,}".format(total_cost))
    print("   Number of Items: {}".format(len(items)))

    print("\n All Items (before sorting):")
    for i, item in enumerate(items, 1):
        print("   {}. {}".format(i, item['name']))
        print(COST_FORMAT.format(item['cost'], item['weight_pct']))

    # Sort items by weight_pct in descending order and take top N
    print("\nSorting items by weight_pct (descending)...")
    sorted_items = sorted(items, key=lambda x: x['weight_pct'], reverse=True)

    print("\nSorted Items:")
    for i, item in enumerate(sorted_items, 1):
        print("   {}. {}".format(i, item['name']))
        print(COST_FORMAT.format(item['cost'], item['weight_pct']))

    top_items = sorted_items[:top_n]

    print("\nTop {} Cost Contributors Selected:".format(len(top_items)))
    for i, item in enumerate(top_items, 1):
        print("   {}. {}".format(i, item['name']))
        print(COST_FORMAT.format(item['cost'], item['weight_pct']))

    print("\nResult prepared with {} top items".format(len(top_items)))
    print("="*60 + "\n")

    # Return result with job metadata and top items
    return {
        'job_id': job_id,
        'job_name': job_name,
        'total_cost': total_cost,
        'top_items': top_items
    }
