from typing import List
from rencanakan_core.models import Ahs
from automatic_job_matching.service.exact_matcher import AhsRow
import logging

logger = logging.getLogger(__name__)

class DbAhsRepository:
    def by_code_like(self, code: str) -> List[AhsRow]:
        logger.debug("by_code_like called with raw code=%s", code)

        variants = {code, code.replace("-", "."), code.replace(".", "-")}
        logger.debug("Querying variants: %s", variants)

        qs = Ahs.objects.none()
        for v in variants:
            logger.debug("Filtering Ahs.code iexact=%s", v)
            qs = qs.union(Ahs.objects.filter(code__iexact=v))
        rows, seen = [], set()
        for a in qs:
            if a.id not in seen:
                rows.append(AhsRow(id=a.id, code=a.code or "", name=a.name or ""))
                seen.add(a.id)

        logger.info("by_code_like found %d unique results", len(rows))
        return rows

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        logger.debug("by_name_candidates called with head_token=%s", head_token)

        qs = Ahs.objects.filter(name__istartswith=head_token)[:200]
        results = [AhsRow(id=a.id, code=(a.code or ""), name=(a.name or "")) for a in qs]
        
        logger.info("by_name_candidates returned %d rows", len(results))
        return results

    def get_all_ahs(self) -> List[AhsRow]:
        logger.debug("get_all_ahs called (limit 1000)")
        
        qs = Ahs.objects.all()[:1000]
        results = [AhsRow(id=a.id, code=(a.code or ""), name=(a.name or "")) for a in qs]
        
        logger.info("get_all_ahs returned %d rows", len(results))
        return results