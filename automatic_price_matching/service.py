from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError

from .ahs_cache import AhsCache
from .fallback_validator import apply_fallback
from .price_retrieval import AhspPriceRetriever, MockAhspSource
from .total_cost import TotalCostCalculator
from .validators import validate_ahsp_payload


class AutomaticPriceMatchingService:
    """Validate payloads, try AHSP lookup, fallback and recalc totals."""

    def __init__(
        self,
        price_retriever: Optional[AhspPriceRetriever] = None,
        cache: Optional[AhsCache] = None,
    ) -> None:
        self.price_retriever = price_retriever or AhspPriceRetriever(MockAhspSource({}))
        self.cache = cache or AhsCache()

    def match_one(self, payload: Any) -> Dict[str, Any]:
        cleaned = validate_ahsp_payload(payload)


        # If caller provided a unit_price (manual override or initial input)
        if cleaned.get("unit_price") is not None:
            user_unit = cleaned.get("unit_price")

            # Detect if the code has a known AHSP price and differs from it
            code = cleaned.get("code", "")
            known_price = self.price_retriever.get_price_by_job_code(code) if code else None
            if known_price is not None and user_unit != known_price:
                match_status = "Overridden"
            else:
                match_status = "Provided"

            cleaned["total_cost"] = TotalCostCalculator.calculate(
                cleaned.get("volume"), user_unit
            )
            cleaned["match_status"] = match_status
            cleaned["is_editable"] = True
            return cleaned

        # Try lookup by code
        code = cleaned.get("code", "")
        price: Optional[Decimal] = None
        if code:
            price = self.price_retriever.get_price_by_job_code(code)

        if price is not None:
            cleaned["unit_price"] = price
            cleaned["total_cost"] = TotalCostCalculator.calculate(cleaned.get("volume"), price)
            cleaned["match_status"] = "Matched"
            cleaned["is_editable"] = False
            return cleaned

        # Fallback
        fb = apply_fallback(cleaned.get("name"))
        cleaned["unit_price"] = fb["unit_price"]
        cleaned["total_cost"] = fb["total_price"]
        cleaned["match_status"] = fb["match_status"]
        cleaned["is_editable"] = fb["is_editable"]
        return cleaned

    def match_batch(self, payloads: List[Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for p in payloads:
            try:
                results.append(self.match_one(p))
            except ValidationError as exc:
                results.append({"error": getattr(exc, "message_dict", str(exc))})
        return results