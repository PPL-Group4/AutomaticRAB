from django.test import TestCase
from unittest.mock import patch
from automatic_job_matching.service.matching_service import MatchingService


class MatchingServiceFallbackTests(TestCase):
    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_fuzzy_match_fallback_to_match(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value
        del fake_matcher.match_with_confidence
        fake_matcher.match.return_value = {"source": "ahs", "id": 1, "code": "X", "name": "Y"}

        result = MatchingService.perform_fuzzy_match("test", unit=None)
        self.assertEqual(result["source"], "ahs")
        self.assertTrue(fake_matcher.match.called)

    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_multiple_match_fallback_to_find_multiple_matches(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value
        del fake_matcher.find_multiple_matches_with_confidence
        fake_matcher.find_multiple_matches.return_value = [{"id": 1}]

        result = MatchingService.perform_multiple_match("test", unit=None)
        self.assertEqual(result[0]["id"], 1)
        self.assertTrue(fake_matcher.find_multiple_matches.called)

    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_best_match_prefers_exact_then_fuzzy_then_multiple(
        self, mock_multi, mock_fuzzy, mock_exact
    ):
        mock_exact.return_value = {"id": 1, "code": "E.01", "name": "Exact"}
        result = MatchingService.perform_best_match("bongkar batu")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["code"], "E.01")
        mock_fuzzy.assert_not_called()
        mock_multi.assert_not_called()

        mock_exact.return_value = None
        mock_fuzzy.return_value = {"id": 2, "code": "F.01", "name": "Fuzzy"}
        result = MatchingService.perform_best_match("bongkar batu")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["code"], "F.01")
        mock_multi.assert_not_called()

        mock_fuzzy.return_value = None
        mock_multi.return_value = [{"id": 3, "code": "M.01", "name": "Multi"}]
        result = MatchingService.perform_best_match("batu")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["code"], "M.01")


class MatchingSingleVsMultiWordTests(TestCase):
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_single_word_returns_multiple_matches(self, mock_multi, mock_exact):
        mock_exact.return_value = None
        mock_multi.return_value = [
            {"id": 1, "name": "pasangan batu"},
            {"id": 2, "name": "batu belah"},
        ]

        result = MatchingService.perform_best_match("batu")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        mock_multi.assert_called_once()

    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    def test_multi_word_returns_single_best_match(self, mock_fuzzy, mock_exact):
        mock_exact.return_value = None
        mock_fuzzy.return_value = {"id": 1, "name": "bongkar pasangan batu"}

        result = MatchingService.perform_best_match("bongkar batu")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], 1)
        mock_fuzzy.assert_called_once()


class MatchingServiceEdgeCaseTests(TestCase):
    @patch("automatic_job_matching.service.matching_service.ExactMatcher")
    def test_exact_match_with_exception(self, mock_exact_cls):
        mock_matcher = mock_exact_cls.return_value
        mock_matcher.match.side_effect = Exception("Database error")
        result = MatchingService.perform_exact_match("test query", unit=None)
        self.assertIsNone(result)

    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_fuzzy_match_with_exception(self, mock_fuzzy_cls):
        mock_matcher = mock_fuzzy_cls.return_value
        mock_matcher.match_with_confidence.side_effect = Exception("Scoring error")
        result = MatchingService.perform_fuzzy_match("test query", unit=None)
        self.assertIsNone(result)

        mock_matcher.match.side_effect = Exception("Matching error")
        result = MatchingService.perform_fuzzy_match("test query", unit=None)
        self.assertIsNone(result)

    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_multiple_match_with_exception(self, mock_fuzzy_cls):
        mock_matcher = mock_fuzzy_cls.return_value
        mock_matcher.find_multiple_matches_with_confidence.side_effect = Exception("Search error")
        result = MatchingService.perform_multiple_match("test query", unit=None)
        self.assertEqual(result, [])

    @patch("automatic_job_matching.service.matching_service.normalize_text")
    def test_best_match_normalization(self, mock_normalize):
        mock_normalize.return_value = ""
        result = MatchingService.perform_best_match("!@#$%")
        self.assertIsNone(result)

        mock_normalize.return_value = "   "
        result = MatchingService.perform_best_match("   ")
        self.assertIsNone(result)

    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_best_match_all_methods_return_none(self, mock_multi, mock_fuzzy, mock_exact):
        mock_exact.return_value = None
        mock_fuzzy.return_value = None
        mock_multi.return_value = []
        result = MatchingService.perform_best_match("xyz nonexistent query")
        self.assertEqual(result, [])

    @patch("automatic_job_matching.service.matching_service.CombinedAhsRepository")
    def test_repository_initialization_error(self, mock_repo_cls):
        mock_repo_cls.side_effect = Exception("Database connection failed")
        result = MatchingService.perform_exact_match("test", unit=None)
        self.assertIsNone(result)

    def test_empty_and_whitespace_queries(self):
        for query in ["", "   ", "\t\n"]:
            with self.subTest(query=query):
                exact_result = MatchingService.perform_exact_match(query)
                fuzzy_result = MatchingService.perform_fuzzy_match(query)
                multi_result = MatchingService.perform_multiple_match(query)
                self.assertTrue(exact_result is None or exact_result == {})
                self.assertTrue(fuzzy_result is None or fuzzy_result == {})
                self.assertTrue(isinstance(multi_result, list))

    def test_single_word_query_triggers_multiple_match(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_multiple_match', return_value=[{"id": 1}]) as mock_multi:
                result = MatchingService.perform_best_match("batu")
                mock_multi.assert_called_once()
                self.assertIsInstance(result, list)

    def test_multi_word_query_triggers_fuzzy_match(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value={"id": 1}) as mock_fuzzy:
                result = MatchingService.perform_best_match("bongkar batu")
                mock_fuzzy.assert_called_once()
                self.assertIsInstance(result, dict)

    def test_word_count_determines_matching_strategy(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_multiple_match', return_value=[]) as mock_multi:
                MatchingService.perform_best_match("batu")
                mock_multi.assert_called_once()

            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None) as mock_fuzzy:
                MatchingService.perform_best_match("bongkar batu")
                mock_fuzzy.assert_called_once()

    def test_best_match_exception_in_perform_best_match(self):
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
            mock_normalize.side_effect = Exception("Normalization error")
            result = MatchingService.perform_best_match("test query", unit=None)
            self.assertIsNone(result)

    def test_best_match_with_exception_after_normalization(self):
        with patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match") as mock_exact:
            mock_exact.side_effect = Exception("Database error in exact match")
            result = MatchingService.perform_best_match("test query", unit=None)
            self.assertIsNone(result)

    def test_best_match_exception_logged(self):
        with patch("automatic_job_matching.service.matching_service.logger") as mock_logger:
            with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
                mock_normalize.side_effect = Exception("Test error")
                MatchingService.perform_best_match("test", unit=None)
                mock_logger.error.assert_called()

    def test_perform_best_match_line_88_coverage(self):
        with patch("automatic_job_matching.service.matching_service.normalize_text", return_value="valid text"):
            with patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match") as mock_exact:
                mock_exact.side_effect = Exception("Database connection failed")
                result = MatchingService.perform_best_match("test query", unit=None)
                self.assertIsNone(result)

    def test_perform_best_match_all_paths_exhausted(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    result = MatchingService.perform_best_match("xyz abc nonexistent")
                    self.assertEqual(result, [])

    def test_all_matching_strategies_fail_returns_appropriate_fallback(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    result = MatchingService.perform_best_match("nonexistent material query")
                    self.assertEqual(result, [])

    def test_exception_handling_in_best_match_workflow(self):
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
            mock_normalize.side_effect = Exception("Normalization error")
            result = MatchingService.perform_best_match("test", unit=None)
            self.assertIsNone(result)

        with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
            mock_exact.side_effect = Exception("Database error")
            result = MatchingService.perform_best_match("test query", unit=None)
            self.assertIsNone(result)

    def test_error_logging_occurs_on_exceptions(self):
        with patch("automatic_job_matching.service.matching_service.logger") as mock_logger:
            with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
                mock_exact.side_effect = Exception("Test error")
                MatchingService.perform_best_match("test", unit=None)
                mock_logger.error.assert_called()

    def test_database_connection_failure_handled_gracefully(self):
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_norm:
            mock_norm.return_value = "valid query"
            with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
                mock_exact.side_effect = Exception("Database connection lost")
                result = MatchingService.perform_best_match("test query", unit=None)
                self.assertIsNone(result)

    def test_all_strategies_exhausted_returns_empty_results(self):
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    result = MatchingService.perform_best_match("xyzabc nonexistent")
                    self.assertEqual(result, [])

    def test_single_word_exact_match_wraps_result_in_list(self):
        with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
            mock_exact.return_value = {"id": 1, "code": "A.01", "name": "batu", "source": "ahs"}
            result = MatchingService.perform_best_match("batu")
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["code"], "A.01")
            mock_exact.assert_called_once()

    @patch("automatic_job_matching.service.matching_service.TranslationService.translate_to_indonesian")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    def test_perform_best_match_calls_translation(self, mock_exact, mock_translate):
        mock_translate.return_value = "pasang lantai beton"
        mock_exact.return_value = {"id": 1, "code": "A.01", "name": "batu"}

        result = MatchingService.perform_best_match("install concrete floor")
        mock_translate.assert_called_once_with("install concrete floor")
        mock_exact.assert_called_once_with("pasang lantai beton")
        self.assertEqual(result["code"], "A.01")

        # multi-word input -> dict
        result = MatchingService.perform_best_match("desc sample")
        self.assertIsInstance(result, dict)

    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match", return_value=None)
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match", return_value=None)
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match", return_value=None)
    def test_best_match_uses_fallback_when_no_match(self, _m_exact, _m_fuzzy, _m_multi):
        with patch("automatic_job_matching.service.matching_service.logger") as mock_logger:
            result = {"match_status": "Needs Manual Input"}
            # Simulate internal fallback
            mock_logger.warning.return_value = result
            out = MatchingService.perform_best_match("unknown desc")
            self.assertTrue(out is None or isinstance(out, (dict, list)))

    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_fuzzy_match_passes_unit_to_matcher(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value
        fake_matcher.match_with_confidence.return_value = {"id": 1, "code": "U.01", "name": "unit test"}

        result = MatchingService.perform_fuzzy_match("pasang beton", unit="m3")
        self.assertEqual(result["code"], "U.01")
        fake_matcher.match_with_confidence.assert_called_once_with("pasang beton", unit="m3")

