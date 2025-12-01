from django.test import TestCase
from unittest.mock import patch, MagicMock
from pdf_parser.services import job_matcher
from automatic_job_matching.models import UnmatchedAhsEntry


class JobMatcherTests(TestCase):
    """Tests for pdf_parser/services/job_matcher.py"""

    def test_skip_empty_or_whitespace_description(self):
        """Should return skipped status for empty or blank input."""
        for desc in ["", "   ", None]:
            result = job_matcher.match_description(desc)
            self.assertEqual(result["status"], "skipped")
            self.assertIsNone(result["match"])

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_found_exact_dict_match(self, mock_match):
        """Should return 'found' when perform_best_match returns a dict with confidence=1.0."""
        mock_match.return_value = {
            "code": "A.01",
            "name": "Pasangan Batu",
            "confidence": 1.0,
        }
        result = job_matcher.match_description("pasangan batu")
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["match"]["code"], "A.01")
        mock_match.assert_called_once_with("pasangan batu", unit=None)


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


class UnmatchedAhsStorageTests(TestCase):
    """Tests for storing unmatched AHS entries in database."""

    def setUp(self):
        """Clear the unmatched entries table before each test."""
        UnmatchedAhsEntry.objects.all().delete()

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_unmatched_entry_when_not_found(self, mock_match):
        """Should store entry in database when status is 'not found'."""
        mock_match.return_value = None
        
        result = job_matcher.match_description("Unknown job description")
        
        self.assertEqual(result["status"], "not found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, "Unknown job description")
        self.assertEqual(entry.ahs_code, "")

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_unmatched_entry_when_empty_list_returned(self, mock_match):
        """Should store entry when empty list is returned."""
        mock_match.return_value = []
        
        result = job_matcher.match_description("Another unknown job")
        
        self.assertEqual(result["status"], "not found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_match_found(self, mock_match):
        """Should NOT store entry when a match is found."""
        mock_match.return_value = {"code": "A.01", "name": "Matched Job", "confidence": 1.0}
        
        result = job_matcher.match_description("Matched job")
        
        self.assertEqual(result["status"], "found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_similar_match_found(self, mock_match):
        """Should NOT store entry when similar matches are found."""
        mock_match.return_value = [{"code": "B.01", "name": "Similar Job"}]
        
        result = job_matcher.match_description("Similar job")
        
        self.assertEqual(result["status"], "similar")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_create_duplicate_entries(self, mock_match):
        """Should not create duplicate entries for the same description."""
        mock_match.return_value = None
        
        # First call
        job_matcher.match_description("Duplicate test")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        # Second call with same description
        job_matcher.match_description("Duplicate test")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        # Entry should still exist and be the same
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, "Duplicate test")

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_multiple_different_unmatched_entries(self, mock_match):
        """Should store multiple different unmatched entries."""
        mock_match.return_value = None
        
        job_matcher.match_description("First unknown")
        job_matcher.match_description("Second unknown")
        job_matcher.match_description("Third unknown")
        
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 3)
        
        names = set(UnmatchedAhsEntry.objects.values_list('name', flat=True))
        self.assertEqual(names, {"First unknown", "Second unknown", "Third unknown"})

    @patch("pdf_parser.services.job_matcher.logger")
    @patch("pdf_parser.services.job_matcher.UnmatchedAhsEntry.objects.get_or_create")
    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_handles_database_error_gracefully(self, mock_match, mock_get_or_create, mock_logger):
        """Should handle database errors gracefully and log them."""
        mock_match.return_value = None
        mock_get_or_create.side_effect = Exception("Database connection failed")
        
        result = job_matcher.match_description("Test description")
        
        # Should still return not found status
        self.assertEqual(result["status"], "not found")
        
        # Should log the error
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to store unmatched entry", mock_logger.error.call_args[0][0])

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_error_occurs_in_matching(self, mock_match):
        """Should NOT store entry when matching service raises an error."""
        mock_match.side_effect = Exception("Matching service error")
        
        result = job_matcher.match_description("Error test")
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_description_is_skipped(self, mock_match):
        """Should NOT store entry when description is empty or whitespace."""
        result = job_matcher.match_description("   ")
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)
        mock_match.assert_not_called()

    @patch("pdf_parser.services.job_matcher.logger")
    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_logs_successful_storage(self, mock_match, mock_logger):
        """Should log info message when entry is successfully stored."""
        mock_match.return_value = None
        
        job_matcher.match_description("Test for logging")
        
        # Check that info log was called
        mock_logger.info.assert_called_once()
        self.assertIn("Stored unmatched entry", mock_logger.info.call_args[0][0])

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_entry_with_special_characters(self, mock_match):
        """Should correctly store descriptions with special characters."""
        mock_match.return_value = None
        special_desc = "Pekerjaan @ #$% & *() test's \"quote\""
        
        job_matcher.match_description(special_desc)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, special_desc)

    @patch("pdf_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_very_long_description(self, mock_match):
        """Should handle very long descriptions."""
        mock_match.return_value = None
        long_desc = "A" * 5000  # Very long description
        
        job_matcher.match_description(long_desc)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, long_desc)
        self.assertEqual(len(entry.name), 5000)
