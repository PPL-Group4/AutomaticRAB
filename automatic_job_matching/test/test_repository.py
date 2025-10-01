from django.test import SimpleTestCase
from unittest.mock import patch
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import AhsRow

class DbAhsRepositoryTests(SimpleTestCase):
    def setUp(self):
        class Dummy:
            id = 1
            code = "T.15.a.1"
            name = "Pemadatan pasir"
        self.fake_ahs = Dummy()

    @patch("rencanakan_core.models.Ahs.objects.none")
    @patch("rencanakan_core.models.Ahs.objects.filter")
    def test_by_code_like_returns_exact_match_and_variants(self, mock_filter, mock_none):
        class FakeQS(list):
            def union(self, other): return FakeQS(self + list(other))

        mock_none.return_value = FakeQS()
        mock_filter.return_value = FakeQS([self.fake_ahs])

        repo = DbAhsRepository()
        rows = repo.by_code_like("T.15.a.1")

        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], AhsRow)
        self.assertEqual(rows[0].code, "T.15.a.1")
        self.assertEqual(rows[0].name, "Pemadatan pasir")

        called_codes = [c.kwargs["code__iexact"] for c in mock_filter.call_args_list]
        self.assertIn("T.15.a.1", called_codes)

    @patch("rencanakan_core.models.Ahs.objects.filter")
    def test_by_name_candidates_istartswith(self, mock_filter):
        class FakeQS(list): pass
        mock_filter.return_value = FakeQS([self.fake_ahs])

        repo = DbAhsRepository()
        rows = repo.by_name_candidates("Pemadatan")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "Pemadatan pasir")
        mock_filter.assert_called_once_with(name__istartswith="Pemadatan")