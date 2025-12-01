from django.test import TestCase
from unittest.mock import patch
from pdf_parser.services import job_matcher


class JobMatcherTests(TestCase):
    """Tests for pdf_parser/services/job_matcher.py"""

    def test_skip_empty_or_whitespace_description(self):
        """Should return skipped status for empty or blank input."""
        for desc in ["", "   ", None]:
            result = job_matcher.match_description(desc)
            self.assertEqual(result["status"], "skipped")
            self.assertIsNone(result["match"])

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_found_similar_single_list(self, mock_match):
        """Should return 'similar' when one similar match is found."""
        mock_match.return_value = [{"code": "B.02", "name": "Batu Belah"}]
        result = job_matcher.match_description("batu")
        self.assertEqual(result["status"], "similar")
        self.assertIsInstance(result["match"], list)
        self.assertEqual(result["match"][0]["code"], "B.02")

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_found_multiple_similar(self, mock_match):
        """Should return 'found X similar' when multiple matches are found."""
        mock_match.return_value = [
            {"code": "C.01", "name": "Batu Belah"},
            {"code": "C.02", "name": "Pasangan Batu"}
        ]
        result = job_matcher.match_description("batu pasangan")
        self.assertEqual(result["status"], "found 2 similar")
        self.assertEqual(len(result["match"]), 2)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_not_found_when_return_none(self, mock_match):
        """Should return 'not found' when no match is returned."""
        mock_match.return_value = None
        result = job_matcher.match_description("tidak ditemukan")
        self.assertEqual(result["status"], "not found")
        self.assertIsNone(result["match"])

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_not_found_when_return_empty_list(self, mock_match):
        """Should return 'not found' when empty list is returned."""
        mock_match.return_value = []
        result = job_matcher.match_description("kosong")
        self.assertEqual(result["status"], "not found")
        self.assertEqual(result["match"], [])

    @patch("pdf_parser.services.job_matcher.logger")
    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_error_handling_on_exception(self, mock_match, mock_logger):
        """Should handle exceptions gracefully and log them."""
        mock_match.side_effect = Exception("Database unavailable")
        result = job_matcher.match_description("test error")
        self.assertEqual(result["status"], "error")
        self.assertIn("Database unavailable", result["error"])
        mock_logger.exception.assert_called_once_with("Job matching failed for description")

    # ---------- Internal function _derive_status ----------
    def test_derive_status_dict_confidence_1(self):
        """_derive_status should return 'found' if confidence == 1.0."""
        match = {"code": "A.01", "name": "Pasangan Batu", "confidence": 1.0}
        self.assertEqual(job_matcher._derive_status(match), "found")

    def test_derive_status_dict_without_confidence(self):
        """_derive_status should return 'similar' if confidence is missing or < 1.0."""
        match = {"code": "A.01", "name": "Pasangan Batu"}
        self.assertEqual(job_matcher._derive_status(match), "similar")

    def test_derive_status_single_list(self):
        """_derive_status should detect single list element as 'similar'."""
        self.assertEqual(job_matcher._derive_status([{"a": 1}]), "similar")

    def test_derive_status_multiple_list(self):
        """_derive_status should detect multiple matches."""
        self.assertEqual(job_matcher._derive_status([{"a": 1}, {"b": 2}]), "found 2 similar")

    def test_derive_status_none_or_empty(self):
        """_derive_status should detect empty or None as 'not found'."""
        self.assertEqual(job_matcher._derive_status(None), "not found")
        self.assertEqual(job_matcher._derive_status([]), "not found")
        self.assertEqual(job_matcher._derive_status({}), "not found")
