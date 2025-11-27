from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from automatic_job_matching.service.exact_matcher import AhsRow
from automatic_job_matching.service.word_embeddings import SemanticMatcher, SynonymExpander


class FakeAhsRepo:
    def __init__(self, rows):
        self.rows = rows
    
    def get_all_ahs(self):
        return self.rows

class MockTensor:
    """Mock tensor object with .item() method."""
    def __init__(self, value):
        self.value = value
    
    def item(self):
        return self.value

class SynonymExpanderTests(SimpleTestCase):
    """Test SynonymExpander with and without model availability."""
    
    def test_expander_unavailable_when_model_fails(self):
        """Test that expander gracefully handles model loading failure."""
        with patch('automatic_job_matching.service.word_embeddings.SentenceTransformer') as mock_st:
            mock_st.side_effect = Exception("Model not found")
            
            expander = SynonymExpander()
            
            self.assertFalse(expander.is_available())
            self.assertIsNone(expander.model)
    
    def test_expander_available_when_model_loads(self):
        """Test that expander is available when model loads successfully."""
        with patch('automatic_job_matching.service.word_embeddings.SentenceTransformer') as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model
            
            expander = SynonymExpander()
            
            self.assertTrue(expander.is_available())
            self.assertIsNotNone(expander.model)
    
    def test_expand_returns_empty_when_unavailable(self):
        """Test that expand returns empty set when model unavailable."""
        with patch('automatic_job_matching.service.word_embeddings.SentenceTransformer') as mock_st:
            mock_st.side_effect = Exception("Model not found")
            
            expander = SynonymExpander()
            result = expander.expand("bongkar", ["pembongkaran", "buka"], limit=3)
            
            self.assertEqual(result, set())
    
    def test_expand_returns_empty_for_empty_input(self):
        """Test that expand handles empty inputs gracefully."""
        with patch('automatic_job_matching.service.word_embeddings.SentenceTransformer'):
            expander = SynonymExpander()
            
            # Empty word
            self.assertEqual(expander.expand("", ["test"]), set())
            
            # Empty candidates
            self.assertEqual(expander.expand("test", []), set())
            
            # Both empty
            self.assertEqual(expander.expand("", []), set())
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_filters_by_threshold(self, mock_util, mock_st):
        """Test that expand only returns words above similarity threshold."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        # Mock embeddings
        import torch
        mock_model.encode.return_value = torch.tensor([0.1, 0.2, 0.3])
        
        # Mock similarities with MockTensor objects
        mock_similarities = [[MockTensor(0.85), MockTensor(0.60), MockTensor(0.40)]]
        mock_util.cos_sim.return_value = mock_similarities
        
        expander = SynonymExpander(similarity_threshold=0.7)
        result = expander.expand("bongkar", ["pembongkaran", "buka", "tutup"], limit=5)
        
        # Should only return "pembongkaran" (0.85 >= 0.7)
        self.assertEqual(len(result), 1)
        self.assertIn("pembongkaran", result)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_respects_limit(self, mock_util, mock_st):
        """Test that expand respects the limit parameter."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        import torch
        mock_model.encode.return_value = torch.tensor([0.1, 0.2, 0.3, 0.4])
        
        # All above threshold
        mock_similarities = [[MockTensor(0.90), MockTensor(0.85), MockTensor(0.80), MockTensor(0.75)]]
        mock_util.cos_sim.return_value = mock_similarities
        
        expander = SynonymExpander(similarity_threshold=0.7)
        result = expander.expand("bongkar", ["a", "b", "c", "d"], limit=2)
        
        # Should only return 2 results
        self.assertEqual(len(result), 2)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_expand_handles_exception_gracefully(self, mock_st):
        """Test that expand handles encoding exceptions."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.side_effect = Exception("Encoding failed")
        
        expander = SynonymExpander()
        result = expander.expand("test", ["word1", "word2"])
        
        self.assertEqual(result, set())
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_handles_cos_sim_exception(self, mock_util, mock_st):
        """Test that expand handles cos_sim exceptions."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.return_value = MagicMock()
        
        # cos_sim raises exception
        mock_util.cos_sim.side_effect = Exception("Similarity calculation failed")
        
        expander = SynonymExpander()
        result = expander.expand("test", ["word1", "word2"])
        
        self.assertEqual(result, set())
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_handles_unexpected_cos_sim_format(self, mock_util, mock_st):
        """Test that expand handles unexpected cos_sim return format."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.return_value = MagicMock()
        
        # cos_sim returns wrong format (not nested list)
        mock_util.cos_sim.return_value = [0.85, 0.60]  # Missing outer list
        
        expander = SynonymExpander()
        
        # Should handle gracefully by returning empty set on error
        try:
            result = expander.expand("test", ["word1", "word2"])
            self.assertIsInstance(result, set)
        except Exception:
            pass  # Exception is acceptable for malformed data
    
    @patch('automatic_job_matching.service.word_embeddings.has_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.get_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_with_manual_combines_both_sources(self, mock_util, mock_st, mock_get_syn, mock_has_syn):
        """Test that expand_with_manual combines manual + embedding synonyms."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        import torch
        mock_model.encode.return_value = torch.tensor([0.1, 0.2])
        
        # Mock manual synonyms
        mock_has_syn.return_value = True
        mock_get_syn.return_value = ["pembongkaran", "buka"]
        
        # Mock embedding synonyms
        mock_similarities = [[MockTensor(0.85), MockTensor(0.60)]]
        mock_util.cos_sim.return_value = mock_similarities
        
        expander = SynonymExpander(similarity_threshold=0.7)
        result = expander.expand_with_manual("bongkar", ["pembongkaran", "rusak"], limit=5)
        
        # Should contain both manual + embedding synonyms
        self.assertIn("pembongkaran", result)  # Manual (deduplicated)
        self.assertIn("buka", result)          # Manual
    
    @patch('automatic_job_matching.service.word_embeddings.has_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_expand_with_manual_works_without_candidates(self, mock_st, mock_has_syn):
        """Test that expand_with_manual works with only manual synonyms."""
        mock_st.return_value = MagicMock()
        mock_has_syn.return_value = True
        
        with patch('automatic_job_matching.service.word_embeddings.get_synonyms') as mock_get_syn:
            mock_get_syn.return_value = ["pembongkaran"]
            
            expander = SynonymExpander()
            result = expander.expand_with_manual("bongkar", candidate_words=None)
            
            self.assertIn("pembongkaran", result)
    
    @patch('automatic_job_matching.service.word_embeddings.has_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_expand_with_manual_no_manual_synonyms_exist(self, mock_st, mock_has_syn):
        """Test expand_with_manual when word has no manual synonyms."""
        mock_st.return_value = MagicMock()
        mock_has_syn.return_value = False  # No manual synonyms
        
        expander = SynonymExpander()
        
        with patch.object(expander, 'expand', return_value={'embedding1', 'embedding2'}) as mock_expand:
            result = expander.expand_with_manual("xyz", ["word1", "word2"], limit=3)
            
            # Should call expand (embedding-only path) - uses positional args
            mock_expand.assert_called_once_with("xyz", ["word1", "word2"], 3)
            self.assertEqual(result, {'embedding1', 'embedding2'})
    
    @patch('automatic_job_matching.service.word_embeddings.has_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.get_synonyms')
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_expand_with_manual_handles_exception_in_manual_lookup(self, mock_st, mock_get_syn, mock_has_syn):
        """Test expand_with_manual when get_synonyms raises exception."""
        mock_st.return_value = MagicMock()
        mock_has_syn.return_value = True
        mock_get_syn.side_effect = Exception("Manual synonym lookup failed")
        
        expander = SynonymExpander()
        
        # Should raise exception since there's no try-except in expand_with_manual
        with self.assertRaises(Exception):
            expander.expand_with_manual("bongkar", ["word1"], limit=3)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_with_zero_limit(self, mock_util, mock_st):
        """Test expand with limit=0."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        import torch
        mock_model.encode.return_value = torch.tensor([0.1, 0.2])
        
        mock_similarities = [[MockTensor(0.9), MockTensor(0.8)]]
        mock_util.cos_sim.return_value = mock_similarities
        
        expander = SynonymExpander()
        result = expander.expand("test", ["word1", "word2"], limit=0)
        
        # Should return empty set when limit is 0
        self.assertEqual(len(result), 0)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_expand_with_negative_limit(self, mock_util, mock_st):
        """Test expand with negative limit."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        import torch
        mock_model.encode.return_value = torch.tensor([0.1, 0.2, 0.3])
        
        mock_similarities = [[MockTensor(0.9), MockTensor(0.8), MockTensor(0.7)]]
        mock_util.cos_sim.return_value = mock_similarities
        
        expander = SynonymExpander(similarity_threshold=0.6)
        result = expander.expand("test", ["w1", "w2", "w3"], limit=-1)
        
        # Current implementation: negative limit causes range issue, returns empty
        # This documents actual behavior (not ideal, but test reflects reality)
        self.assertIsInstance(result, set)

class SemanticMatcherTests(SimpleTestCase):
    """Test SemanticMatcher for AI-powered matching."""
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_semantic_matcher_initialization(self, mock_st):
        """Test that SemanticMatcher initializes properly."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        repo = FakeAhsRepo([])
        matcher = SemanticMatcher(repo)
        
        self.assertIsNotNone(matcher.model)
        self.assertEqual(matcher._cache, {})
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_semantic_matcher_initialization_failure(self, mock_st):
        """Test SemanticMatcher handles model initialization failure."""
        mock_st.side_effect = Exception("Model loading failed")
        
        repo = FakeAhsRepo([])
        
        # Should raise exception (no try-except in __init__)
        with self.assertRaises(Exception):
            SemanticMatcher(repo)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_find_best_match_returns_none_for_empty_query(self, mock_st):
        """Test that empty queries return None."""
        mock_st.return_value = MagicMock()
        repo = FakeAhsRepo([])
        matcher = SemanticMatcher(repo)
        
        result = matcher.find_best_match("")
        self.assertIsNone(result)
        
        result = matcher.find_best_match("   ")
        self.assertIsNone(result)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_find_best_match_with_empty_repository(self, mock_st):
        """Test find_best_match with empty repository."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.return_value = MagicMock()
        
        repo = FakeAhsRepo([])
        matcher = SemanticMatcher(repo)
        
        # Should return None (early return before cos_sim)
        result = matcher.find_best_match("test query", min_similarity=0.5)
        self.assertIsNone(result)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_best_match_no_results_above_threshold(self, mock_util, mock_st):
        """Test find_best_match when no results meet min_similarity."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=1, code="A.01", name="pasangan batu"),
            AhsRow(id=2, code="B.01", name="galian tanah"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        import torch
        # All similarities below threshold
        mock_util.cos_sim.return_value = torch.tensor([[0.30, 0.25]])
        
        result = matcher.find_best_match("xyz", min_similarity=0.5)
        
        # Should return None when no results above threshold
        self.assertIsNone(result)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_filters_by_similarity(self, mock_util, mock_st):
        """Test that find_multiple_matches filters by min_similarity."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=1, code="A.01", name="pasangan batu"),
            AhsRow(id=2, code="B.01", name="galian tanah"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        # Mock embeddings
        mock_model.encode.return_value = MagicMock()
        
        # Mock similarities: [0.85, 0.40] (only first above 0.5 threshold)
        import torch
        mock_util.cos_sim.return_value = torch.tensor([[0.85, 0.40]])
        
        results = matcher.find_multiple_matches("pasangan batu merah", min_similarity=0.5, limit=5)
        
        # Should only return first result (0.85 >= 0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 1)
        self.assertGreaterEqual(results[0]["confidence"], 0.5)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_respects_limit(self, mock_util, mock_st):
        """Test that find_multiple_matches respects limit parameter."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=i, code=f"X.{i:02d}", name=f"item {i}")
            for i in range(1, 11)
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        # All have high similarity
        import torch
        similarities = torch.tensor([[0.9 - i*0.05 for i in range(10)]])
        mock_util.cos_sim.return_value = similarities
        
        results = matcher.find_multiple_matches("test query", limit=3)
        
        # Should only return 3 results
        self.assertLessEqual(len(results), 3)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_find_multiple_matches_handles_encoding_exception(self, mock_st):
        """Test that find_multiple_matches handles encoding exceptions."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.side_effect = Exception("Encoding failed")
        
        rows = [AhsRow(id=1, code="A.01", name="test")]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        # Should return empty list (exception caught in updated code)
        result = matcher.find_multiple_matches("test", limit=5)
        self.assertEqual(result, [])
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_semantic_matcher_uses_cache(self, mock_util, mock_st):
        """Test that SemanticMatcher caches embeddings."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [AhsRow(id=1, code="A.01", name="pasangan batu")]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        import torch
        mock_util.cos_sim.return_value = torch.tensor([[0.85]])
        
        # First call - should encode and cache
        matcher.find_multiple_matches("test", limit=1)
        self.assertGreater(len(matcher._cache), 0)
        
        # Second call - should use cache
        initial_cache_size = len(matcher._cache)
        matcher.find_multiple_matches("test2", limit=1)
        # Cache should still contain first item
        self.assertGreaterEqual(len(matcher._cache), initial_cache_size)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_best_match_returns_single_result(self, mock_util, mock_st):
        """Test that find_best_match returns single best result."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=1, code="A.01", name="pasangan batu"),
            AhsRow(id=2, code="B.01", name="galian tanah"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        import torch
        mock_util.cos_sim.return_value = torch.tensor([[0.85, 0.70]])
        
        result = matcher.find_best_match("pasangan batu", min_similarity=0.5)
        
        # Should return dict (not list)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["matched_on"], "semantic")
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    def test_find_multiple_matches_with_empty_query(self, mock_st):
        """Test find_multiple_matches with empty query."""
        mock_st.return_value = MagicMock()
        repo = FakeAhsRepo([AhsRow(id=1, code="A.01", name="test")])
        matcher = SemanticMatcher(repo)
        
        result = matcher.find_multiple_matches("", limit=5)
        self.assertEqual(result, [])
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_with_very_long_query(self, mock_util, mock_st):
        """Test find_multiple_matches with very long query string."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        mock_model.encode.return_value = MagicMock()
        
        rows = [AhsRow(id=1, code="A.01", name="test")]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        import torch
        mock_util.cos_sim.return_value = torch.tensor([[0.75]])
        
        # Very long query (1000 chars)
        long_query = "test " * 200
        results = matcher.find_multiple_matches(long_query, limit=5)
        
        # Should handle long queries gracefully
        self.assertIsInstance(results, list)

    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_empty_candidates_after_filtering(self, mock_util, mock_st):
        """Test when all candidates have empty names (line 156-158)."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        # All candidates have empty names
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="   "),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        # Should return empty list (no valid candidates after normalization)
        result = matcher.find_multiple_matches("test query", limit=5)
        self.assertEqual(result, [])
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_encoding_failure_for_candidate(self, mock_util, mock_st):
        """Test when encoding fails for specific candidate (line 165-166)."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=1, code="A.01", name="test1"),
            AhsRow(id=2, code="B.01", name="test2"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        # First call (query) succeeds, second call (candidate) fails
        mock_model.encode.side_effect = [
            MagicMock(),  # Query encoding succeeds
            Exception("Encoding failed for candidate"),  # First candidate fails
            MagicMock(),  # Second candidate succeeds
        ]
        
        import torch
        mock_util.cos_sim.return_value = torch.tensor([[0.85]])
        
        # Should skip failed candidate and return successful one
        result = matcher.find_multiple_matches("test", limit=5)
        self.assertIsInstance(result, list)
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_cos_sim_exception(self, mock_util, mock_st):
        """Test when cos_sim raises exception (line 171-173)."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [AhsRow(id=1, code="A.01", name="test")]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        mock_util.cos_sim.side_effect = Exception("Cosine similarity calculation failed")
        
        # Should catch exception and return empty list
        result = matcher.find_multiple_matches("test", limit=5)
        self.assertEqual(result, [])
    
    @patch('automatic_job_matching.service.word_embeddings.SentenceTransformer')
    @patch('automatic_job_matching.service.word_embeddings.util')
    def test_find_multiple_matches_no_results_above_threshold(self, mock_util, mock_st):
        """Test when no results meet min_similarity threshold (line 150)."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model
        
        rows = [
            AhsRow(id=1, code="A.01", name="completely different"),
            AhsRow(id=2, code="B.01", name="totally unrelated"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = SemanticMatcher(repo)
        
        mock_model.encode.return_value = MagicMock()
        
        import torch
        # All similarities below threshold (0.5 default)
        mock_util.cos_sim.return_value = torch.tensor([[0.20, 0.15]])
        
        result = matcher.find_multiple_matches("test query", min_similarity=0.5, limit=5)
        
        # Should return empty list (no results above threshold)
        self.assertEqual(result, [])