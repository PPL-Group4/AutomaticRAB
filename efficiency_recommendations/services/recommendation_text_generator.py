from typing import Dict, Optional


def generate_recommendation_text(highest_item: Optional[Dict]) -> str:
    """
    Generates recommendation text for the highest cost-weight item.
    Returns an empty string if the highest item is None.
    """
    if not highest_item:
        return ""

    item_name = highest_item.get('name', 'Unknown Item')
    weight_pct = highest_item.get('weight_pct', 0)
    percentage_str = f"{float(weight_pct):.2f}"

    return (
        f"{item_name} accounts for {percentage_str}% of the total cost. "
        f"Consider evaluating material prices for this job."
    )
