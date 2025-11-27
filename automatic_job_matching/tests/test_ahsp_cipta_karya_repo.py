from unittest.mock import mock_open, patch

from django.test import SimpleTestCase

from automatic_job_matching.repository.ahsp_cipta_karya_repo import AhspCiptaKaryaRepository
from automatic_job_matching.service.exact_matcher import AhsRow

SAMPLE_CSV = (
    ";NO;URAIAN PEKERJAAN;SATUAN;HARGA SATUAN;KETERANGAN;;;\n"
    ";5.1.1.1.31;Pemasangan 1 m’ Kabel NYY 3 x 35 mm²;m';Rp100; -;;\n"
    ";5.1.1.1.24;Pemasangan 1 m’ Kabel NYY 3 x 1,5 mm2;m';Rp50; -;;\n"
    ";;;;;;;\n"
)

class AhspCiptaKaryaRepositoryTests(SimpleTestCase):
    def _repo(self):
        return AhspCiptaKaryaRepository()

    @patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CSV)
    def test_load_csv_parses_rows_and_normalizes(self, mopen):
        repo = self._repo()
        rows = repo._load_csv()

        self.assertEqual(len(rows), 2)

        first: AhsRow = rows[0]
        self.assertIsInstance(first, AhsRow)
        self.assertEqual(first.code, "5.1.1.1.31".replace("-", ".").replace(" ", ""))  
        self.assertEqual(first.name, "pemasangan 1 m' kabel nyy 3 x 35 mm2")

    @patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CSV)
    def test_by_code_like_returns_expected_match(self, mopen):
        repo = self._repo()
        results = repo.by_code_like("5.1.1.1.31")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "5.1.1.1.31")
        self.assertIn("kabel nyy 3 x 35 mm2", results[0].name)

    @patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CSV)
    def test_by_name_candidates_returns_expected_match(self, mopen):
        repo = self._repo()
        q = "Pemasangan 1 m’ Kabel NYY 3 x 35 mm²"
        results = repo.by_name_candidates(q)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "5.1.1.1.31")

    @patch("builtins.open", new_callable=mock_open, read_data=SAMPLE_CSV)
    def test_get_all_ahs_returns_all_rows(self, mopen):
        repo = self._repo()
        all_rows = repo.get_all_ahs()
        self.assertEqual(len(all_rows), 2)
        codes = {r.code for r in all_rows}
        self.assertEqual(codes, {"5.1.1.1.31", "5.1.1.1.24"})

    @patch("builtins.open", new_callable=mock_open, read_data="")  
    def test_load_csv_missing_or_empty_returns_empty_list(self, mopen):
        repo = self._repo()
        rows = repo._load_csv()
        self.assertEqual(rows, [])
