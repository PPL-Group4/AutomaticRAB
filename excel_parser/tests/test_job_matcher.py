from django.test import TestCase
from unittest.mock import patch

from excel_parser.services.job_matcher import _derive_status, match_description
from automatic_job_matching.models import UnmatchedAhsEntry


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


class UnmatchedAhsStorageTests(TestCase):
    """Tests for storing unmatched AHS entries in database."""

    def setUp(self):
        """Clear the unmatched entries table before each test."""
        UnmatchedAhsEntry.objects.all().delete()

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_unmatched_entry_when_not_found(self, mock_match):
        """Should store entry in database when status is 'not found'."""
        mock_match.return_value = None
        
        result = match_description("Unknown material")
        
        self.assertEqual(result["status"], "not found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, "Unknown material")
        self.assertEqual(entry.ahs_code, "")

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_unmatched_entry_when_empty_dict_returned(self, mock_match):
        """Should store entry when empty dict is returned."""
        mock_match.return_value = {}
        
        result = match_description("Empty dict test")
        
        self.assertEqual(result["status"], "not found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_unmatched_entry_when_empty_list_returned(self, mock_match):
        """Should store entry when empty list is returned."""
        mock_match.return_value = []
        
        result = match_description("Empty list test")
        
        self.assertEqual(result["status"], "not found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_match_found(self, mock_match):
        """Should NOT store entry when a match is found."""
        mock_match.return_value = {"code": "A.01", "name": "Matched Material"}
        
        result = match_description("Matched material")
        
        self.assertEqual(result["status"], "found")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_similar_match_found(self, mock_match):
        """Should NOT store entry when similar matches are found."""
        mock_match.return_value = [{"code": "B.01", "name": "Similar Material"}]
        
        result = match_description("Similar material")
        
        self.assertEqual(result["status"], "similar")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_multiple_similar_matches_found(self, mock_match):
        """Should NOT store entry when multiple similar matches are found."""
        mock_match.return_value = [
            {"code": "C.01", "name": "Material 1"},
            {"code": "C.02", "name": "Material 2"}
        ]
        
        result = match_description("Multiple matches")
        
        self.assertEqual(result["status"], "found 2 similar")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_create_duplicate_entries(self, mock_match):
        """Should not create duplicate entries for the same description."""
        mock_match.return_value = None
        
        # First call
        match_description("Duplicate excel test")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        # Second call with same description
        match_description("Duplicate excel test")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 1)
        
        # Entry should still exist
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, "Duplicate excel test")

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_multiple_different_unmatched_entries(self, mock_match):
        """Should store multiple different unmatched entries."""
        mock_match.return_value = None
        
        match_description("Material A")
        match_description("Material B")
        match_description("Material C")
        
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 3)
        
        names = set(UnmatchedAhsEntry.objects.values_list('name', flat=True))
        self.assertEqual(names, {"Material A", "Material B", "Material C"})

    @patch("excel_parser.services.job_matcher.logger")
    @patch("excel_parser.services.job_matcher.UnmatchedAhsEntry.objects.get_or_create")
    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_handles_database_error_gracefully(self, mock_match, mock_get_or_create, mock_logger):
        """Should handle database errors gracefully and log them."""
        mock_match.return_value = None
        mock_get_or_create.side_effect = Exception("Database error")
        
        result = match_description("Test material")
        
        # Should still return not found status
        self.assertEqual(result["status"], "not found")
        
        # Should log the error
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to store unmatched entry", mock_logger.error.call_args[0][0])

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_error_occurs_in_matching(self, mock_match):
        """Should NOT store entry when matching service raises an error."""
        mock_match.side_effect = RuntimeError("Service error")
        
        result = match_description("Error test")
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_description_is_skipped(self, mock_match):
        """Should NOT store entry when description is blank."""
        result = match_description("   ")
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)
        mock_match.assert_not_called()

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_does_not_store_when_description_is_none(self, mock_match):
        """Should NOT store entry when description is None."""
        result = match_description(None)
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(UnmatchedAhsEntry.objects.count(), 0)
        mock_match.assert_not_called()

    @patch("excel_parser.services.job_matcher.logger")
    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_logs_successful_storage(self, mock_match, mock_logger):
        """Should log info message when entry is successfully stored."""
        mock_match.return_value = None
        
        match_description("Log test material")
        
        # Check that info log was called
        mock_logger.info.assert_called_once()
        self.assertIn("Stored unmatched entry", mock_logger.info.call_args[0][0])

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_entry_with_unicode_characters(self, mock_match):
        """Should correctly store descriptions with unicode characters."""
        mock_match.return_value = None
        unicode_desc = "Bahan 材料 مادة ñ é ü"
        
        match_description(unicode_desc)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, unicode_desc)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_stores_entry_with_newlines_and_tabs(self, mock_match):
        """Should handle descriptions with newlines and tabs."""
        mock_match.return_value = None
        multiline_desc = "Line 1\nLine 2\tTabbed"
        
        match_description(multiline_desc)
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.name, multiline_desc)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_timestamp_is_set_on_creation(self, mock_match):
        """Should set created_at timestamp when entry is created."""
        mock_match.return_value = None
        
        match_description("Timestamp test")
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertIsNotNone(entry.created_at)

    @patch("excel_parser.services.job_matcher.MatchingService.perform_best_match")
    def test_ahs_code_is_empty_by_default(self, mock_match):
        """Should have empty ahs_code field by default."""
        mock_match.return_value = None
        
        match_description("Empty code test")
        
        entry = UnmatchedAhsEntry.objects.first()
        self.assertEqual(entry.ahs_code, "")
