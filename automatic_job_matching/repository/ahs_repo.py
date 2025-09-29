from typing import List
from rencanakan_core.models import Ahs
from automatic_job_matching.service.exact_matcher import AhsRow

class DbAhsRepository:
    def by_code_like(self, code: str) -> List[AhsRow]:
        variants = {code, code.replace("-", "."), code.replace(".", "-")}
        qs = Ahs.objects.none()
        for v in variants:
            qs = qs.union(Ahs.objects.filter(code__iexact=v))
        rows, seen = [], set()
        for a in qs:
            if a.id not in seen:
                rows.append(AhsRow(id=a.id, code=a.code or "", name=a.name or ""))
                seen.add(a.id)
        return rows

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        qs = Ahs.objects.filter(name__istartswith=head_token)[:200]
        return [AhsRow(id=a.id, code=(a.code or ""), name=(a.name or "")) for a in qs]

    def get_all_ahs(self) -> List[AhsRow]:
        qs = Ahs.objects.all()[:1000]
        return [AhsRow(id=a.id, code=(a.code or ""), name=(a.name or "")) for a in qs]
