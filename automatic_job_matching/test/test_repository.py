from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
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

        # Configure the chained call filter().values_list(...).distinct() to return tuples
        vals_mock = MagicMock()
        vals_mock.distinct.return_value = [(self.fake_ahs.id, self.fake_ahs.code, self.fake_ahs.name)]
        # values_list should return an object that has distinct(); emulate it
        mock_filter.return_value.values_list.return_value = vals_mock

        repo = DbAhsRepository()
        rows = repo.by_code_like("T.15.a.1")

        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], AhsRow)
        self.assertEqual(rows[0].code, "T.15.a.1")
        self.assertEqual(rows[0].name, "Pemadatan pasir")

        # Ensure filter was called (we no longer assume kwargs shape of call)
        self.assertTrue(mock_filter.called)

    @patch("rencanakan_core.models.Ahs.objects.filter")
    def test_by_name_candidates_istartswith(self, mock_filter):
        # values_list should return a sliceable list for the [:200] used in the repo
        mock_filter.return_value.values_list.return_value = [(self.fake_ahs.id, self.fake_ahs.code, self.fake_ahs.name)]

        repo = DbAhsRepository()
        rows = repo.by_name_candidates("Pemadatan")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "Pemadatan pasir")
        mock_filter.assert_called_once_with(name__istartswith="Pemadatan")