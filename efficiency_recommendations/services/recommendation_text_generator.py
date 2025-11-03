from typing import Dict


def generate_recommendation_text(highest_item: Dict) -> str:
    item_name = highest_item['name']
    weight_pct = highest_item['weight_pct']
    
    # Format percentage to 2 decimal places
    percentage_str = f"{float(weight_pct):.2f}"
    
    # Generate recommendation text following PBI requirement format
    text = (
        f"{item_name} accounts for {percentage_str}% of the total cost. "
        f"Consider evaluating material prices for this job."
    )
    
    return text
