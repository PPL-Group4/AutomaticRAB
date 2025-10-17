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
        # Test 1: Exact match (multi-word query to get single result)
        mock_exact.return_value = {"id": 1, "code": "E.01", "name": "Exact"}
        result = MatchingService.perform_best_match("bongkar batu")  # Multi-word
        self.assertIsInstance(result, dict)
        self.assertEqual(result["code"], "E.01")
        mock_fuzzy.assert_not_called()
        mock_multi.assert_not_called()

        # Test 2: Fuzzy match (multi-word query)
        mock_exact.return_value = None
        mock_fuzzy.return_value = {"id": 2, "code": "F.01", "name": "Fuzzy"}
        result = MatchingService.perform_best_match("bongkar batu")  # Multi-word
        self.assertIsInstance(result, dict)
        self.assertEqual(result["code"], "F.01")
        mock_multi.assert_not_called()

        # Test 3: Multiple match (single-word query returns list)
        mock_fuzzy.return_value = None
        mock_multi.return_value = [{"id": 3, "code": "M.01", "name": "Multi"}]
        result = MatchingService.perform_best_match("batu")  # Single word
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["code"], "M.01")


class MatchingSingleVsMultiWordTests(TestCase):
    """Test single-word vs multi-word query handling."""
    
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_single_word_returns_multiple_matches(self, mock_multi, mock_exact):
        """Test that single-word queries return multiple matches."""
        mock_exact.return_value = None
        mock_multi.return_value = [
            {"id": 1, "name": "pasangan batu"},
            {"id": 2, "name": "batu belah"},
        ]
        
        result = MatchingService.perform_best_match("batu")
        
        # Should return list for single-word query
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        mock_multi.assert_called_once()
    
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    def test_multi_word_returns_single_best_match(self, mock_fuzzy, mock_exact):
        """Test that multi-word queries return single best match."""
        mock_exact.return_value = None
        mock_fuzzy.return_value = {"id": 1, "name": "bongkar pasangan batu"}
        
        result = MatchingService.perform_best_match("bongkar batu")
        
        # Should return single match (not list) for multi-word query
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], 1)
        mock_fuzzy.assert_called_once()


class MatchingServiceEdgeCaseTests(TestCase):
    """Test edge cases and error handling in MatchingService."""
    
    @patch("automatic_job_matching.service.matching_service.ExactMatcher")
    def test_exact_match_with_exception(self, mock_exact_cls):
        """Test that exceptions in exact_match are handled gracefully."""
        mock_matcher = mock_exact_cls.return_value
        mock_matcher.match.side_effect = Exception("Database error")
        
        # Should not crash, should return None
        result = MatchingService.perform_exact_match("test query")
        self.assertIsNone(result)
    
    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_fuzzy_match_with_exception(self, mock_fuzzy_cls):
        """Test that exceptions in fuzzy_match are handled gracefully."""
        mock_matcher = mock_fuzzy_cls.return_value
        
        # Test match_with_confidence exception
        mock_matcher.match_with_confidence.side_effect = Exception("Scoring error")
        result = MatchingService.perform_fuzzy_match("test query")
        self.assertIsNone(result)
        
        # Test fallback to match() also fails
        mock_matcher.match.side_effect = Exception("Matching error")
        result = MatchingService.perform_fuzzy_match("test query")
        self.assertIsNone(result)
    
    @patch("automatic_job_matching.service.matching_service.FuzzyMatcher")
    def test_multiple_match_with_exception(self, mock_fuzzy_cls):
        """Test that exceptions in multiple_match are handled gracefully."""
        mock_matcher = mock_fuzzy_cls.return_value
        mock_matcher.find_multiple_matches_with_confidence.side_effect = Exception("Search error")
        
        result = MatchingService.perform_multiple_match("test query")
        self.assertEqual(result, [])
    
    @patch("automatic_job_matching.service.matching_service.normalize_text")
    def test_best_match_normalization(self, mock_normalize):
        """Test that normalization is applied in perform_best_match."""
        # Test empty normalization result
        mock_normalize.return_value = ""
        result = MatchingService.perform_best_match("!@#$%")
        self.assertIsNone(result)  # Returns None for empty normalized text
        
        # Test whitespace normalization
        mock_normalize.return_value = "   "
        result = MatchingService.perform_best_match("   ")
        self.assertIsNone(result)  # Returns None for whitespace-only
    
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_fuzzy_match")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_multiple_match")
    def test_best_match_all_methods_return_none(self, mock_multi, mock_fuzzy, mock_exact):
        """Test when all matching methods return None/empty."""
        mock_exact.return_value = None
        mock_fuzzy.return_value = None
        mock_multi.return_value = []
        
        # Multi-word query (>1 word) - returns result from perform_multiple_match
        result = MatchingService.perform_best_match("xyz nonexistent query")
        
        # Should return empty list from perform_multiple_match (last fallback)
        self.assertEqual(result, [])
    
    @patch("automatic_job_matching.service.matching_service.DbAhsRepository")
    def test_repository_initialization_error(self, mock_repo_cls):
        """Test that repository initialization errors are handled."""
        mock_repo_cls.side_effect = Exception("Database connection failed")
        
        # Should not crash, returns None due to exception handling
        result = MatchingService.perform_exact_match("test")
        self.assertIsNone(result)
    
    def test_empty_and_whitespace_queries(self):
        """Test various empty/whitespace query formats."""
        test_cases = ["", "   ", "\t\n"]
        
        for query in test_cases:
            with self.subTest(query=query):
                # Should not crash and should return None or empty list
                exact_result = MatchingService.perform_exact_match(query)
                fuzzy_result = MatchingService.perform_fuzzy_match(query)
                multi_result = MatchingService.perform_multiple_match(query)
                
                # All should handle gracefully
                self.assertTrue(
                    exact_result is None or exact_result == {},
                    f"Exact match failed for query: {repr(query)}"
                )
                self.assertTrue(
                    fuzzy_result is None or fuzzy_result == {},
                    f"Fuzzy match failed for query: {repr(query)}"
                )
                self.assertTrue(
                    isinstance(multi_result, list),
                    f"Multi match should return list for query: {repr(query)}"
                )
    
    def test_single_word_query_triggers_multiple_match(self):
        """Test that single-word queries route to multiple_match."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_multiple_match', return_value=[{"id": 1}]) as mock_multi:
                result = MatchingService.perform_best_match("batu")
                
                # Should call multiple_match for single word
                mock_multi.assert_called_once()
                self.assertIsInstance(result, list)
    
    def test_multi_word_query_triggers_fuzzy_match(self):
        """Test that multi-word queries route to fuzzy_match."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value={"id": 1}) as mock_fuzzy:
                result = MatchingService.perform_best_match("bongkar batu")
                
                # Should call fuzzy_match for multi-word
                mock_fuzzy.assert_called_once()
                self.assertIsInstance(result, dict)
    
    def test_word_count_determines_matching_strategy(self):
        """Test that word count determines single vs multi-word strategy."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            # Single word -> multiple_match
            with patch.object(MatchingService, 'perform_multiple_match', return_value=[]) as mock_multi:
                MatchingService.perform_best_match("batu")
                mock_multi.assert_called_once()
            
            # Multi word -> fuzzy_match
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None) as mock_fuzzy:
                MatchingService.perform_best_match("bongkar batu")
                mock_fuzzy.assert_called_once()

    def test_best_match_exception_in_perform_best_match(self):
        """Test that exceptions in perform_best_match are caught (line 88, 110-112)."""
        # Mock normalize_text to raise exception
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
            mock_normalize.side_effect = Exception("Normalization error")
            
            # Should not crash, should return None
            result = MatchingService.perform_best_match("test query")
            self.assertIsNone(result)
    
    def test_best_match_with_exception_after_normalization(self):
        """Test exception handling after normalization passes (line 110-112)."""
        # Mock perform_exact_match to raise exception
        with patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match") as mock_exact:
            mock_exact.side_effect = Exception("Database error in exact match")
            
            # Should catch exception and return None
            result = MatchingService.perform_best_match("test query")
            self.assertIsNone(result)
    
    def test_best_match_exception_logged(self):
        """Test that exceptions are logged properly."""
        with patch("automatic_job_matching.service.matching_service.logger") as mock_logger:
            with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
                mock_normalize.side_effect = Exception("Test error")
                
                MatchingService.perform_best_match("test")
                
                # Verify error was logged
                mock_logger.error.assert_called()
    
    def test_perform_best_match_line_88_coverage(self):
        """Test perform_best_match exception at line 88 (after normalization)."""
        # Mock normalize_text to succeed, but perform_exact_match to fail
        with patch("automatic_job_matching.service.matching_service.normalize_text", return_value="valid text"):
            with patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match") as mock_exact:
                mock_exact.side_effect = Exception("Database connection failed")
                
                # Should catch exception and return None
                result = MatchingService.perform_best_match("test query")
                self.assertIsNone(result)
    
    def test_perform_best_match_all_paths_exhausted(self):
        """Test when all matching strategies fail (full coverage of line 88-112)."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    # Multi-word query exhausts all strategies
                    result = MatchingService.perform_best_match("xyz abc nonexistent")
                    
                    # Should return empty list (last fallback)
                    self.assertEqual(result, [])

    def test_all_matching_strategies_fail_returns_appropriate_fallback(self):
        """Test behavior when all matching strategies fail."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    # Multi-word query should try all strategies
                    result = MatchingService.perform_best_match("nonexistent material query")
                    
                    # Should return empty list (final fallback)
                    self.assertEqual(result, [])
    
    def test_exception_handling_in_best_match_workflow(self):
        """Test that exceptions during matching workflow are handled."""
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_normalize:
            # Test exception during normalization
            mock_normalize.side_effect = Exception("Normalization error")
            result = MatchingService.perform_best_match("test")
            self.assertIsNone(result)
        
        with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
            # Test exception after normalization
            mock_exact.side_effect = Exception("Database error")
            result = MatchingService.perform_best_match("test query")
            self.assertIsNone(result)
    
    def test_error_logging_occurs_on_exceptions(self):
        """Test that errors are properly logged."""
        with patch("automatic_job_matching.service.matching_service.logger") as mock_logger:
            with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
                mock_exact.side_effect = Exception("Test error")
                
                MatchingService.perform_best_match("test")
                
                # Verify error was logged
                mock_logger.error.assert_called()

    def test_database_connection_failure_handled_gracefully(self):
        """Test that database errors don't crash the matching service."""
        with patch("automatic_job_matching.service.matching_service.normalize_text") as mock_norm:
            mock_norm.return_value = "valid query"
            
            with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
                mock_exact.side_effect = Exception("Database connection lost")
                
                # Should handle error and return None instead of crashing
                result = MatchingService.perform_best_match("test query")
                self.assertIsNone(result)
    
    def test_all_strategies_exhausted_returns_empty_results(self):
        """Test behavior when no matching strategy finds results."""
        with patch.object(MatchingService, 'perform_exact_match', return_value=None):
            with patch.object(MatchingService, 'perform_fuzzy_match', return_value=None):
                with patch.object(MatchingService, 'perform_multiple_match', return_value=[]):
                    
                    # Obscure query that doesn't match anything
                    result = MatchingService.perform_best_match("xyzabc nonexistent")
                    
                    # Should return empty list as final fallback
                    self.assertEqual(result, [])
    
    def test_single_word_exact_match_wraps_result_in_list(self):
        """Test that single-word exact matches are wrapped in list for consistency."""
        with patch.object(MatchingService, 'perform_exact_match') as mock_exact:
            # Mock exact match returning a single result
            mock_exact.return_value = {
                "id": 1,
                "code": "A.01",
                "name": "batu",
                "source": "ahs"
            }
            
            # Single-word query
            result = MatchingService.perform_best_match("batu")
            
            # Should wrap single exact result in list (line 88)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["code"], "A.01")
            mock_exact.assert_called_once()

    @patch("automatic_job_matching.service.matching_service.TranslationService.translate_to_indonesian")
    @patch("automatic_job_matching.service.matching_service.MatchingService.perform_exact_match")
    def test_perform_best_match_calls_translation(self, mock_exact, mock_translate):
        """Test that perform_best_match calls translation before matching."""
        mock_translate.return_value = "pasang lantai beton"
        mock_exact.return_value = {"id": 1, "code": "A.01", "name": "batu"}
        
        result = MatchingService.perform_best_match("install concrete floor")

        mock_translate.assert_called_once_with("install concrete floor")

        mock_exact.assert_called_once_with("pasang lantai beton")

        self.assertEqual(result["code"], "A.01")

    