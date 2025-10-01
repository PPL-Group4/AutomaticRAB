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