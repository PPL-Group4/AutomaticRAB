import logging
from typing import List
from django.db.models import Q
from rencanakan_core.models import Ahs
from automatic_job_matching.service.exact_matcher import AhsRow
from automatic_price_matching.ahs_cache import AhsCache

import logging

logger = logging.getLogger(__name__)

class DbAhsRepository:
    def __init__(self):
        self.cache = AhsCache()

    def by_code_like(self, code: str) -> List[AhsRow]:
        cached = self.cache.get_by_code(code)
        if cached is not None:
            logger.debug("Cache hit for code=%s (len=%d)", code, len(cached))
            return cached

        logger.debug("by_code_like called with raw code=%s", code)

        dot_variant = code.replace("-", ".")
        dash_variant = code.replace(".", "-")
        variants = {code, dot_variant, dash_variant}
        logger.debug("Querying variants: %s", variants)

        q_filter = Q()
        for variant in variants:
            q_filter |= Q(code__iexact=variant)

        # fetch minimal columns via values_list to avoid model instantiation overhead
        qs = Ahs.objects.filter(q_filter).values_list("id", "code", "name").distinct()
        rows = [AhsRow(id=r[0], code=(r[1] or ""), name=(r[2] or "")) for r in qs]

        logger.info("by_code_like found %d unique results", len(rows))
        self.cache.set_by_code(code, rows)
        return rows

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        logger.debug("DB:by_name_candidates called with head_token=%s", head_token)

        # Use prefix search (istartswith) so the B-tree index can be used.
        qs = (
            Ahs.objects
            .filter(name__istartswith=head_token)
            .values_list("id", "code", "name")[:200]
        )
        results = [AhsRow(id=r[0], code=(r[1] or ""), name=(r[2] or "")) for r in qs]
        logger.info("by_name_candidates returned %d rows", len(results))
        return results

    def get_all_ahs(self) -> List[AhsRow]:
        logger.debug("get_all_ahs called")
        
        qs = Ahs.objects.all()[:5000]
        results = [AhsRow(id=a.id, code=(a.code or ""), name=(a.name or "")) for a in qs]
        
        logger.info("get_all_ahs returned %d rows", len(results))
        return results

    def search(self, term: str, limit: int = 10) -> List[AhsRow]:
        cleaned = (term or "").strip()
        if not cleaned:
            logger.debug("search called with empty term")
            return []

        logger.debug("search called term=%s limit=%d", cleaned, limit)

        qs = (
            Ahs.objects
            .filter(Q(code__icontains=cleaned) | Q(name__icontains=cleaned))
            .order_by("code")
        )[:max(1, min(limit, 50))]

        rows = [AhsRow(id=a.id, code=a.code or "", name=a.name or "") for a in qs]
        logger.info("search returned %d rows", len(rows))
        return rows
