from typing import Dict


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
    print(f"\n{'='*60}")
    print(f"IDENTIFYING TOP {top_n} COST CONTRIBUTORS")
    print(f"{'='*60}")

    # Extract job metadata
    job_id = job_data['job_id']
    job_name = job_data['job_name']
    total_cost = job_data['total_cost']
    items = job_data['items']

    print("\nJob Information:")
    print(f"   Job ID: {job_id}")
    print(f"   Job Name: {job_name}")
    print(f"   Total Cost: Rp {total_cost:,}")
    print(f"   Number of Items: {len(items)}")

    print("\n All Items (before sorting):")
    for i, item in enumerate(items, 1):
        print(f"   {i}. {item['name']}")
        print(f"      Cost: Rp {item['cost']:,} ({item['weight_pct']}%)")

    # Sort items by weight_pct in descending order and take top N
    print("\nSorting items by weight_pct (descending)...")
    sorted_items = sorted(items, key=lambda x: x['weight_pct'], reverse=True)

    print("\nSorted Items:")
    for i, item in enumerate(sorted_items, 1):
        print(f"   {i}. {item['name']}")
        print(f"      Cost: Rp {item['cost']:,} ({item['weight_pct']}%)")

    top_items = sorted_items[:top_n]

    print(f"\nTop {len(top_items)} Cost Contributors Selected:")
    for i, item in enumerate(top_items, 1):
        print(f"   {i}. {item['name']}")
        print(f"      Cost: Rp {item['cost']:,} ({item['weight_pct']}%)")

    print(f"\nResult prepared with {len(top_items)} top items")
    print(f"{'='*60}\n")

    # Return result with job metadata and top items
    return {
        'job_id': job_id,
        'job_name': job_name,
        'total_cost': total_cost,
        'top_items': top_items
    }
