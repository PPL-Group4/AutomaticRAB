import logging
from typing import List
from django.db.models import Q
from rencanakan_core.models import Ahs
from automatic_job_matching.service.exact_matcher import AhsRow

logger = logging.getLogger(__name__)

class DbAhsRepository:
    def by_code_like(self, code: str) -> List[AhsRow]:
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
        return rows

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        logger.debug("by_name_candidates called with head_token=%s", head_token)

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
        qs = Ahs.objects.all().values_list("id", "code", "name")
        return [AhsRow(id=r[0], code=(r[1] or ""), name=(r[2] or "")) for r in qs]
