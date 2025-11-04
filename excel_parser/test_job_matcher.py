from unittest import TestCase
from unittest.mock import patch

from excel_parser.services.job_matcher import _derive_status, match_description


class DeriveStatusTests(TestCase):
    def test_returns_found_for_non_empty_dict(self):
        self.assertEqual(_derive_status({"code": "X"}), "found")

    def test_returns_similar_for_single_list_match(self):
        self.assertEqual(_derive_status([{"code": "X"}]), "similar")

    def test_returns_found_count_for_multiple_matches(self):
        self.assertEqual(_derive_status([1, 2, 3]), "found 3 similar")

    def test_returns_not_found_for_other_values(self):
        self.assertEqual(_derive_status(None), "not found")

    def test_returns_not_found_for_empty_dict(self):
        self.assertEqual(_derive_status({}), "not found")

    def test_returns_not_found_for_empty_list(self):
        self.assertEqual(_derive_status([]), "not found")


class MatchDescriptionTests(TestCase):
    def test_returns_skipped_for_blank_description(self):
        result = match_description("   ")
        self.assertEqual(result, {"status": "skipped", "match": None})

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_match_payload_from_service(self, mock_match):
        mock_match.return_value = {"code": "A.1", "name": "Sample"}

        result = match_description("Mobilisasi")

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["match"], {"code": "A.1", "name": "Sample"})
        mock_match.assert_called_once_with("Mobilisasi")

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_similar_for_single_list_match(self, mock_match):
        mock_match.return_value = [{"code": "B.1", "name": "Similar"}]

        result = match_description("Mobilisasi")

        self.assertEqual(result["status"], "similar")
        self.assertEqual(result["match"], [{"code": "B.1", "name": "Similar"}])

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_found_count_for_multiple_matches(self, mock_match):
        mock_match.return_value = [
            {"code": "C.1"},
            {"code": "C.2"},
        ]

        result = match_description("Mobilisasi")

        self.assertEqual(result["status"], "found 2 similar")
        self.assertEqual(len(result["match"]), 2)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_not_found_when_service_returns_none(self, mock_match):
        mock_match.return_value = None

        result = match_description("Mobilisasi")

        self.assertEqual(result, {"status": "not found", "match": None})

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_not_found_when_service_returns_empty_dict(self, mock_match):
        mock_match.return_value = {}

        result = match_description("Mobilisasi")

        self.assertEqual(result, {"status": "not found", "match": {}})

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_returns_not_found_when_service_returns_empty_list(self, mock_match):
        mock_match.return_value = []

        result = match_description("Mobilisasi")

        self.assertEqual(result, {"status": "not found", "match": []})

    def test_returns_skipped_for_none_description(self):
        self.assertEqual(match_description(None), {"status": "skipped", "match": None})

    @patch("excel_parser.services.job_matcher.logger")
    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match", side_effect=RuntimeError("boom"))
    def test_returns_error_when_service_fails(self, _mock_match, mock_logger):
        result = match_description("Mobilisasi")

        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["match"])
        self.assertEqual(result["error"], "boom")
        mock_logger.exception.assert_called_once()
