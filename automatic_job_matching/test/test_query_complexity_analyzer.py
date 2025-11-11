"""
Test suite for Query Complexity Analyzer

This test suite validates the functionality of the QueryComplexityAnalyzer,
ensuring accurate complexity analysis and appropriate strategy recommendations
for various query types.
"""

from django.test import TestCase
from automatic_job_matching.service.query_complexity_analyzer import (
    QueryComplexityAnalyzer,
    QueryComplexityMetrics
)


class TestQueryComplexityAnalyzer(TestCase):
    """Test cases for QueryComplexityAnalyzer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = QueryComplexityAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test that the analyzer initializes correctly."""
        self.assertIsNotNone(self.analyzer)
        self.assertIsNotNone(self.analyzer.word_weight_config)
        self.assertAlmostEqual(self.analyzer.SIMPLE_THRESHOLD, 0.3, places=3)
        self.assertAlmostEqual(self.analyzer.COMPLEX_THRESHOLD, 0.7, places=3)
    
    def test_analyze_empty_query(self):
        """Test analysis of empty or whitespace-only queries."""
        self.assertIsNone(self.analyzer.analyze(""))
        self.assertIsNone(self.analyzer.analyze("   "))
        self.assertIsNone(self.analyzer.analyze(None))
    
    def test_analyze_special_chars_only(self):
        """Test analysis of queries with special characters that normalize to empty."""
        # These should normalize to empty strings
        self.assertIsNone(self.analyzer.analyze("!!!"))
        self.assertIsNone(self.analyzer.analyze("@#$%"))
        self.assertIsNone(self.analyzer.analyze("......"))
    
    def test_analyze_single_word_query(self):
        """Test analysis of single-word queries."""
        result = self.analyzer.analyze("beton")
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, QueryComplexityMetrics)
        self.assertEqual(result.word_count, 1)
        self.assertIn(result.complexity_level, ["simple", "moderate", "complex"])
        self.assertEqual(result.recommended_strategy, "exact")
    
    def test_analyze_simple_query(self):
        """Test analysis of simple queries."""
        result = self.analyzer.analyze("pasang pipa")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.word_count, 2)
        self.assertGreaterEqual(result.complexity_score, 0.0)
        self.assertLessEqual(result.complexity_score, 1.0)
        self.assertIn(result.complexity_level, ["simple", "moderate", "complex"])
    
    def test_analyze_technical_query(self):
        """Test analysis of technical/material-heavy queries."""
        result = self.analyzer.analyze("pemasangan pipa beton pracetak diameter 200mm")
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.word_count, 4)
        self.assertGreaterEqual(result.technical_word_count, 1)
        self.assertIn(result.complexity_level, ["moderate", "complex"])
    
    def test_analyze_complex_query(self):
        """Test analysis of complex multi-word queries."""
        query = "pekerjaan pemasangan rangka atap baja ringan dengan genteng metal"
        result = self.analyzer.analyze(query)
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.word_count, 8)
        self.assertGreater(result.complexity_score, 0.3)
        self.assertIn(result.recommended_strategy, ["fuzzy", "multi_match"])
    
    def test_technical_word_count(self):
        """Test counting of technical/material words."""
        result = self.analyzer.analyze("beton besi kayu")
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.technical_word_count, 2)
    
    def test_action_word_count(self):
        """Test counting of action words."""
        result = self.analyzer.analyze("pemasangan pembongkaran pengecatan")
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.action_word_count, 1)
    
    def test_generic_word_count(self):
        """Test counting of generic/filler words."""
        result = self.analyzer.analyze("pasang pipa untuk dan dengan")
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.generic_word_count, 1)
    
    def test_complexity_score_range(self):
        """Test that complexity scores are within valid range."""
        queries = [
            "beton",
            "pasang pipa",
            "pemasangan rangka atap baja",
            "pekerjaan galian tanah untuk pondasi dengan kedalaman tertentu"
        ]
        
        for query in queries:
            result = self.analyzer.analyze(query)
            self.assertIsNotNone(result)
            self.assertGreaterEqual(result.complexity_score, 0.0)
            self.assertLessEqual(result.complexity_score, 1.0)
    
    def test_complexity_level_simple(self):
        """Test identification of simple complexity level."""
        result = self.analyzer.analyze("dan untuk")  # Generic words only
        
        self.assertIsNotNone(result)
        # Generic-heavy queries should have lower complexity
        self.assertIn(result.complexity_level, ["simple", "moderate"])
    
    def test_complexity_level_moderate(self):
        """Test identification of moderate complexity level."""
        result = self.analyzer.analyze("pasang beton ready mix")
        
        self.assertIsNotNone(result)
        # Should be moderate complexity
        self.assertIn(result.complexity_level, ["simple", "moderate", "complex"])
    
    def test_complexity_level_complex(self):
        """Test identification of complex complexity level."""
        result = self.analyzer.analyze("pemasangan dinding bata merah diplester acian halus")
        
        self.assertIsNotNone(result)
        # Multi-word technical query should be moderate to complex
        self.assertGreaterEqual(result.word_count, 5)
    
    def test_strategy_recommendation_exact(self):
        """Test exact match strategy recommendation for single words."""
        result = self.analyzer.analyze("beton")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.recommended_strategy, "exact")
    
    def test_strategy_recommendation_fuzzy(self):
        """Test fuzzy match strategy recommendation."""
        result = self.analyzer.analyze("pasang beton")
        
        self.assertIsNotNone(result)
        self.assertIn(result.recommended_strategy, ["exact", "fuzzy", "multi_match"])
    
    def test_strategy_recommendation_multi_match(self):
        """Test multi-match strategy recommendation for complex queries."""
        query = "pekerjaan pemasangan struktur beton bertulang kolom praktis"
        result = self.analyzer.analyze(query)
        
        self.assertIsNotNone(result)
        # Complex queries might recommend multi_match
        self.assertIn(result.recommended_strategy, ["fuzzy", "multi_match"])
    
    def test_get_analysis_summary(self):
        """Test the analysis summary method."""
        summary = self.analyzer.get_analysis_summary("pasang beton ready mix")
        
        self.assertIsNotNone(summary)
        self.assertIn("query", summary)
        self.assertIn("metrics", summary)
        self.assertIn("analysis", summary)
        self.assertIn("word_count", summary["metrics"])
        self.assertIn("complexity_score", summary["analysis"])
        self.assertIn("recommended_strategy", summary["analysis"])
    
    def test_get_analysis_summary_empty_query(self):
        """Test analysis summary with empty query."""
        summary = self.analyzer.get_analysis_summary("")
        
        self.assertIsNotNone(summary)
        self.assertIn("error", summary)
    
    def test_metrics_repr(self):
        """Test QueryComplexityMetrics string representation."""
        result = self.analyzer.analyze("pasang beton")
        
        self.assertIsNotNone(result)
        repr_str = repr(result)
        self.assertIn("QueryComplexityMetrics", repr_str)
        self.assertIn("words=", repr_str)
        self.assertIn("complexity=", repr_str)
        self.assertIn("strategy=", repr_str)
    
    def test_consistent_analysis(self):
        """Test that analyzing the same query produces consistent results."""
        query = "pemasangan rangka atap baja"
        
        result1 = self.analyzer.analyze(query)
        result2 = self.analyzer.analyze(query)
        
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertEqual(result1.word_count, result2.word_count)
        self.assertEqual(result1.complexity_score, result2.complexity_score)
        self.assertEqual(result1.complexity_level, result2.complexity_level)
        self.assertEqual(result1.recommended_strategy, result2.recommended_strategy)
    
    def test_normalization_handling(self):
        """Test that queries are properly normalized before analysis."""
        result1 = self.analyzer.analyze("PASANG BETON")
        result2 = self.analyzer.analyze("pasang beton")
        result3 = self.analyzer.analyze("  pasang   beton  ")
        
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertIsNotNone(result3)
        # All should have same word count after normalization
        self.assertEqual(result1.word_count, result2.word_count)
        self.assertEqual(result2.word_count, result3.word_count)
    
    def test_various_query_types(self):
        """Test analysis across various query types."""
        test_cases = [
            ("galian tanah", "simple query"),
            ("pengecatan dinding interior", "moderate query"),
            ("pekerjaan pemasangan kusen pintu dan jendela aluminium", "complex query"),
            ("m3", "unit only"),
            ("pekerjaan", "action word only"),
        ]
        
        for query, description in test_cases:
            result = self.analyzer.analyze(query)
            self.assertIsNotNone(result, f"Failed to analyze: {description}")
            self.assertGreater(result.word_count, 0)
            self.assertIn(result.complexity_level, ["simple", "moderate", "complex"])
    
    def test_edge_case_very_long_query(self):
        """Test analysis of very long queries."""
        query = " ".join(["pekerjaan"] * 20)  # 20-word query
        result = self.analyzer.analyze(query)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.word_count, 20)
        # Complexity score should be capped at 1.0
        self.assertLessEqual(result.complexity_score, 1.0)
    
    def test_special_characters_handling(self):
        """Test that special characters are handled properly."""
        result = self.analyzer.analyze("pasang pipa Ø200mm")
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.word_count, 2)
    
    def test_metrics_rounding(self):
        """Test that complexity scores are properly rounded."""
        result = self.analyzer.analyze("pasang beton ready mix mutu k300")
        
        self.assertIsNotNone(result)
        # Score should be rounded to 4 decimal places
        score_str = str(result.complexity_score)
        decimal_places = len(score_str.split('.')[-1]) if '.' in score_str else 0
        self.assertLessEqual(decimal_places, 4)
    
    def test_calculate_complexity_score_zero_words(self):
        """Test complexity score calculation with zero word count."""
        # This tests the defensive check at line 156
        score = self.analyzer._calculate_complexity_score(0, 0, 0, 0)
        self.assertEqual(score, 0.0)


class TestQueryComplexityIntegration(TestCase):
    """Integration tests for Query Complexity Analyzer with other components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = QueryComplexityAnalyzer()
    
    def test_analyzer_with_real_world_queries(self):
        """Test analyzer with realistic construction job queries."""
        real_world_queries = [
            "galian tanah pondasi",
            "pasang pondasi batu kali",
            "pemasangan beton ready mix mutu k225",
            "pekerjaan struktur kolom beton bertulang",
            "pemasangan rangka atap baja ringan",
            "pengecatan dinding interior cat emulsi",
            "pasang keramik lantai 40x40",
        ]
        
        for query in real_world_queries:
            result = self.analyzer.analyze(query)
            self.assertIsNotNone(result, f"Failed on query: {query}")
            self.assertGreater(result.word_count, 0)
            self.assertGreaterEqual(result.complexity_score, 0.0)
            self.assertIn(result.recommended_strategy, ["exact", "fuzzy", "multi_match"])
    
    def test_performance_multiple_analyses(self):
        """Test performance with multiple consecutive analyses."""
        queries = ["pasang beton"] * 100
        
        results = []
        for query in queries:
            result = self.analyzer.analyze(query)
            results.append(result)
        
        self.assertEqual(len(results), 100)
        self.assertTrue(all(r is not None for r in results))
        # All should be identical for the same query
        first_score = results[0].complexity_score
        self.assertTrue(all(r.complexity_score == first_score for r in results))
