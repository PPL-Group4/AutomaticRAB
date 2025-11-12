from typing import Dict, Tuple
from decimal import Decimal

EMPTY_MSG = "No BoQ items available. Recommendations and charts are not generated."
ZERO_MSG = "Total cost is zero. Recommendations and charts are not generated."

def check_boq_health(job_data: Dict) -> Tuple[bool, str]:
    """
    Returns (is_ok, message). is_ok=False means UI should show a friendly
    empty state and skip downstream computations.
    """
    items = job_data.get("items") or []
    total_cost = Decimal(str(job_data.get("total_cost", "0") or "0"))

    if not items:
        return (False, EMPTY_MSG)
    if total_cost == 0:
        return (False, ZERO_MSG)
    return (True, "")
