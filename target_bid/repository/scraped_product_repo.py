import logging
from typing import List, Dict
from django.db.models import Q
from target_bid.models.scraped_product import (
    JuraganMaterialProduct,
    Mitra10Product,
    TokopediaProduct,
    GemilangProduct,
)

logger = logging.getLogger(__name__)


class ScrapedProductRepository:
    def __init__(self):
        self.sources = [
            JuraganMaterialProduct,
            Mitra10Product,
            TokopediaProduct,
            GemilangProduct,
        ]

    def find_cheaper_same_unit(self, name: str, unit: str, current_price: float, limit: int = 5) -> List[Dict]:
        """
        Search for cheaper alternatives with the same unit and similar name across all sources.
        """
        logger.info(
            "Searching cheaper alternatives for '%s' (unit=%s, price=%s)",
            name, unit, current_price,
        )

        words = [w for w in name.split() if len(w) > 2][:3]  # pick first few useful words
        filters = Q(unit__iexact=unit) & Q(price__lt=current_price)

        results = []

        for model in self.sources:
            q = model.objects.using("scraper").filter(filters)
            for w in words:
                q = q.filter(name__icontains=w)
            items = q.values("name", "price", "unit", "url", "category")[:limit]
            for item in items:
                item["source"] = model._meta.db_table
                results.append(item)

        results.sort(key=lambda x: x["price"])
        logger.info("Found %d cheaper alternatives", len(results))
        return results[:limit]
