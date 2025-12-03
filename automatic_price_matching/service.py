from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError

from .validators import validate_ahsp_payload
from .fallback_validator import apply_fallback
from .total_cost import TotalCostCalculator
from .ahs_cache import AhsCache
from .price_retrieval import AhspPriceRetriever, MockAhspSource

import sentry_sdk
from automatic_price_matching.monitoring import (
    record_fallback,
    record_price_override,
    record_missing_price,
    record_cost_anomaly,
    record_batch_errors,
)


class AutomaticPriceMatchingService:
    """Validate payloads, try AHSP lookup, fallback and recalc totals."""

    def __init__(
            self,
            price_retriever: Optional[AhspPriceRetriever] = None,
            cache: Optional[AhsCache] = None,
    ) -> None:
        from .price_retrieval import CombinedAhspSource

        self.price_retriever = price_retriever or AhspPriceRetriever(CombinedAhspSource())
        self.cache = cache or AhsCache()

    def match_one(self, payload: Any) -> Dict[str, Any]:
        with sentry_sdk.start_span(op="price_matching", description="match_one"):
            cleaned = validate_ahsp_payload(payload)
            code = cleaned.get("code", "")
            name = cleaned.get("name", "")

            # Case: User-provided price (override or initial)
            if cleaned.get("unit_price") is not None:
                user_price = cleaned["unit_price"]
                known_price = self.price_retriever.get_price_by_job_code(code) if code else None

                print("CLEANED PAYLOAD =", cleaned)
                print("RAW CODE =", cleaned.get("code"))
                print("CANONICALIZED CODE =", code)
                print("KNOWN PRICE =", known_price, type(known_price))
                print("USER PRICE =", user_price, type(user_price))

                print("KNOWN PRICE =", known_price, "USER PRICE =", user_price, type(user_price))

                # Detect and record override
                if known_price is not None and user_price != known_price:
                    record_price_override(code, known_price, user_price)

                cost = TotalCostCalculator.calculate(cleaned.get("volume"), user_price)
                record_cost_anomaly(cost, cleaned.get("volume"), user_price, code)

                cleaned["total_cost"] = cost
                cleaned["match_status"] = "Overridden" if known_price and user_price != known_price else "Provided"
                cleaned["is_editable"] = True
                return cleaned

            # Case: Lookup AHSP price
            price: Optional[Decimal] = None
            if code:
                with sentry_sdk.start_span(op="price_lookup", description=f"lookup_{code}"):
                    price = self.price_retriever.get_price_by_job_code(code)

                if price is None:
                    record_missing_price(code)

            # Found AHSP match
            if price is not None:
                cost = TotalCostCalculator.calculate(cleaned.get("volume"), price)
                record_cost_anomaly(cost, cleaned.get("volume"), price, code)

                cleaned["unit_price"] = price
                cleaned["total_cost"] = cost
                cleaned["match_status"] = "Matched"
                cleaned["is_editable"] = False
                return cleaned

            # Case: Fallback
            record_fallback(code, name)
            fb = apply_fallback(name)
            cleaned["unit_price"] = fb["unit_price"]
            cleaned["total_cost"] = fb["total_price"]
            cleaned["match_status"] = fb["match_status"]
            cleaned["is_editable"] = fb["is_editable"]
            return cleaned

    def match_batch(self, payloads: List[Any]) -> List[Dict[str, Any]]:
        with sentry_sdk.start_span(op="price_batch", description="match_batch"):
            results: List[Dict[str, Any]] = []
            errors = 0

            for p in payloads:
                try:
                    results.append(self.match_one(p))
                except ValidationError as exc:
                    errors += 1
                    results.append({"error": getattr(exc, "message_dict", str(exc))})

            if errors > 0:
                record_batch_errors(len(payloads), errors)

            return results
