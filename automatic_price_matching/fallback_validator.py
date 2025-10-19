from decimal import Decimal

def apply_fallback(description: str) -> dict:
    return {
        "uraian": description,
        "unit_price": None,
        "total_price": Decimal("0"),
        "match_status": "Needs Manual Input",
        "is_editable": True,
    }
