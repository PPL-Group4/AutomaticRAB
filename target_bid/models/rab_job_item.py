from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

@dataclass(frozen=True)
class RabJobItem:
    rab_item_id: int
    name: str
    unit_name: Optional[str]
    unit_price: Optional[Decimal]
    volume: Optional[Decimal]
    total_price: Optional[Decimal]
    rab_item_header_id: Optional[int]
    rab_item_header_name: Optional[str]
    custom_ahs_id: Optional[int]
    analysis_code: Optional[str]
    is_locked: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "id": self.rab_item_id,
            "name": self.name,
            "unit": self.unit_name,
            "unit_price": DecimalAdapter.to_string(self.unit_price),
            "volume": DecimalAdapter.to_string(self.volume),
            "total_price": DecimalAdapter.to_string(self.total_price),
            "rab_item_header_id": self.rab_item_header_id,
            "rab_item_header_name": self.rab_item_header_name,
            "custom_ahs_id": self.custom_ahs_id,
            "analysis_code": self.analysis_code,
            "is_locked": self.is_locked,
        }

class DecimalAdapter:
    @staticmethod
    def to_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def multiply(left, right):
        if left is None or right is None:
            return None
        return left * right

    @staticmethod
    def to_string(value):
        if value is None:
            return None
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
