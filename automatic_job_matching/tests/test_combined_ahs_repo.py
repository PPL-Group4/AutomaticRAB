from unittest.mock import patch

from django.test import SimpleTestCase

from automatic_job_matching.repository.combined_ahs_repo import CombinedAhsRepository
from automatic_job_matching.service.exact_matcher import AhsRow

DB_ROWS = [
    AhsRow(id=1, code="T.15.a.1", name="pemadatan pasir"),
    AhsRow(id=2, code="5.1.1.1.24", name="pemasangan 1 m' kabel nyy 3 x 1,5 mm2"),
]
CSV_ROWS = [
    AhsRow(id=1001, code="5.1.1.1.31", name="pemasangan 1 m' kabel nyy 3 x 35 mm2"),
    AhsRow(id=1002, code="T.15.a.1", name="pemadatan pasir (csv dup)"),
]

class CombinedAhsRepositoryTests(SimpleTestCase):
    @patch("automatic_job_matching.repository.combined_ahs_repo.DbAhsRepository")
    @patch("automatic_job_matching.repository.combined_ahs_repo.AhspCiptaKaryaRepository")
    def test_by_code_like_merges_db_and_csv_results(self, MockCsvRepo, MockDbRepo):
        db = MockDbRepo.return_value
        csv = MockCsvRepo.return_value
        db.by_code_like.return_value = [DB_ROWS[0]] 
        csv.by_code_like.return_value = [CSV_ROWS[1]]  

        repo = CombinedAhsRepository()
        merged = repo.by_code_like("T.15.a.1")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].code, "T.15.a.1")
        db.by_code_like.assert_called_once_with("T.15.a.1")
        csv.by_code_like.assert_called_once_with("T.15.a.1")

    @patch("automatic_job_matching.repository.combined_ahs_repo.DbAhsRepository")
    @patch("automatic_job_matching.repository.combined_ahs_repo.AhspCiptaKaryaRepository")
    def test_by_name_candidates_merges_and_deduplicates(self, MockCsvRepo, MockDbRepo):
        db = MockDbRepo.return_value
        csv = MockCsvRepo.return_value

        db.by_name_candidates.return_value = [DB_ROWS[1]]  
        csv.by_name_candidates.return_value = [CSV_ROWS[0]] 

        repo = CombinedAhsRepository()
        merged = repo.by_name_candidates("Pemasangan 1 m' kabel NYY")

        self.assertEqual({r.code for r in merged}, {"5.1.1.1.24", "5.1.1.1.31"})
        db.by_name_candidates.assert_called_once()
        csv.by_name_candidates.assert_called_once()

    @patch("automatic_job_matching.repository.combined_ahs_repo.DbAhsRepository")
    @patch("automatic_job_matching.repository.combined_ahs_repo.AhspCiptaKaryaRepository")
    def test_get_all_ahs_merges_and_deduplicates(self, MockCsvRepo, MockDbRepo):
        db = MockDbRepo.return_value
        csv = MockCsvRepo.return_value

        db.get_all_ahs.return_value = DB_ROWS
        csv.get_all_ahs.return_value = CSV_ROWS

        repo = CombinedAhsRepository()
        merged = repo.get_all_ahs()

        self.assertEqual(len({r.code for r in merged}), 3)
        db.get_all_ahs.assert_called_once()
        csv.get_all_ahs.assert_called_once()