from django.test import TestCase
from unittest.mock import patch
from automatic_job_matching.service.matching_service import MatchingService

class MatchingServiceFallbackTests(TestCase):
    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_fuzzy_match_fallback_to_match(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value

        del fake_matcher.match_with_confidence
        fake_matcher.match.return_value = {"source": "ahs", "id": 1, "code": "X", "name": "Y"}
        
        result = MatchingService.perform_fuzzy_match("test")
        self.assertEqual(result["source"], "ahs")
        self.assertTrue(fake_matcher.match.called)

    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_multiple_match_fallback_to_find_multiple_matches(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value
        del fake_matcher.find_multiple_matches_with_confidence
        fake_matcher.find_multiple_matches.return_value = [{"id": 1}]
        
        result = MatchingService.perform_multiple_match("test")
        self.assertEqual(result[0]["id"], 1)
        self.assertTrue(fake_matcher.find_multiple_matches.called)

    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_best_match_prefers_exact_then_fuzzy_then_multiple(
        self, mock_multi, mock_fuzzy, mock_exact
    ):
        mock_exact.return_value = {"id": 1, "code": "E.01", "name": "Exact"}
        result = MatchingService.perform_best_match("desc")
        self.assertEqual(result["code"], "E.01")
        mock_fuzzy.assert_not_called()
        mock_multi.assert_not_called()

        mock_exact.return_value = None
        mock_fuzzy.return_value = {"id": 2, "code": "F.01", "name": "Fuzzy"}
        result = MatchingService.perform_best_match("desc")
        self.assertEqual(result["code"], "F.01")
        mock_multi.assert_not_called()

        mock_fuzzy.return_value = None
        mock_multi.return_value = [{"id": 3, "code": "M.01", "name": "Multi"}]
        result = MatchingService.perform_best_match("desc")
        self.assertEqual(result[0]["code"], "M.01")

    @patch("automatic_job_matching.service.matching_service.apply_fallback")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match", return_value=None)
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match", return_value=None)
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match", return_value=None)
    def test_best_match_uses_fallback_when_no_match(self, _m_exact, _m_fuzzy, _m_multi, mock_fallback):
        mock_fallback.return_value = {"match_status": "Needs Manual Input"}

        result = MatchingService.perform_best_match("unknown desc")

        self.assertEqual(result["match_status"], "Needs Manual Input")
        mock_fallback.assert_called_once_with("unknown desc")


class MatchingServiceSearchTests(TestCase):
    @patch("automatic_job_matching.service.matching_service.DbAhsRepository.search")
    def test_search_candidates_returns_serialised_rows(self, mock_search):
        mock_search.return_value = [
            type("Row", (), {"id": 5, "code": "C.1", "name": "Cor"})(),
            type("Row", (), {"id": 6, "code": "C.2", "name": "Cor Beton"})(),
        ]

        results = MatchingService.search_candidates("Cor", limit=3)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["code"], "C.1")
        mock_search.assert_called_once_with("Cor", 3)

    @patch("automatic_job_matching.service.matching_service.DbAhsRepository.search")
    def test_search_candidates_handles_empty_results(self, mock_search):
        mock_search.return_value = []

        results = MatchingService.search_candidates("", limit=2)

        self.assertEqual(results, [])
        mock_search.assert_called_once_with("", 2)

    @patch("automatic_job_matching.service.matching_service.DbAhsRepository.search", side_effect=RuntimeError("boom"))
    def test_search_candidates_raises_when_repo_fails(self, mock_search):
        with self.assertRaises(RuntimeError):
            MatchingService.search_candidates("Cor")
        mock_search.assert_called_once_with("Cor", 10)