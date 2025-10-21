from typing import List
from automatic_job_matching.service.exact_matcher import AhsRow
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.repository.ahsp_cipta_karya_repo import AhspCiptaKaryaRepository


class CombinedAhsRepository:
    def __init__(self):
        self.db_repo = DbAhsRepository()
        self.csv_repo = AhspCiptaKaryaRepository()

    def _merge_unique(self, list1: List[AhsRow], list2: List[AhsRow]) -> List[AhsRow]:
        merged, seen_codes = [], set()
        for r in list1 + list2:
            if r.code not in seen_codes:
                merged.append(r)
                seen_codes.add(r.code)
        return merged

    def by_code_like(self, code: str) -> List[AhsRow]:
        db_rows = self.db_repo.by_code_like(code)
        csv_rows = self.csv_repo.by_code_like(code)
        merged = self._merge_unique(db_rows, csv_rows)
        return merged

    def by_name_candidates(self, head_token: str) -> List[AhsRow]:
        db_rows = self.db_repo.by_name_candidates(head_token)
        csv_rows = self.csv_repo.by_name_candidates(head_token)
        merged = self._merge_unique(db_rows, csv_rows)
        return merged

    def get_all_ahs(self) -> List[AhsRow]:
        db_rows = self.db_repo.get_all_ahs()
        csv_rows = self.csv_repo.get_all_ahs()
        merged = self._merge_unique(db_rows, csv_rows)
        return merged