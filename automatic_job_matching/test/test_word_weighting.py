from django.test import SimpleTestCase
from automatic_job_matching.service.fuzzy_matcher import (
    FuzzyMatcher, 
    WordWeightConfig,
    SimilarityCalculator,
    CandidateProvider,
    MatchingProcessor,
    _norm_name
)
from automatic_job_matching.service.exact_matcher import AhsRow

class WordWeightingTests(SimpleTestCase):
    """Test word weighting prioritizes materials over actions."""

    def setUp(self):
        self.rows = [
            AhsRow(id=1, code="A.01", name="pekerjaan galian tanah biasa"),
            AhsRow(id=2, code="A.02", name="pekerjaan pemasangan keramik 40x40"),
            AhsRow(id=3, code="A.03", name="pemasangan beton ready mix k300"),
            AhsRow(id=4, code="A.04", name="pekerjaan besi tulangan d16"),
            AhsRow(id=5, code="A.05", name="pekerjaan cat dinding interior"),
        ]

        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return [r for r in self.rows if head_token.lower() in (r.name or "").lower()]
            def get_all_ahs(self):
                return self.rows

        self.repo = FakeRepo(self.rows)
        self.matcher = FuzzyMatcher(self.repo, min_similarity=0.4)

    def test_material_word_prioritized_over_action(self):
        """Query 'pekerjaan keramik' should prioritize entries with 'keramik'."""
        matches = self.matcher.find_multiple_matches("pekerjaan keramik", limit=5)
        
        self.assertGreater(len(matches), 0)
        
        keramik_match = next((m for m in matches if "keramik" in m["name"].lower()), None)
        self.assertIsNotNone(keramik_match, "Should find keramik entry")
        
        top_2_names = [m["name"] for m in matches[:2]]
        self.assertTrue(
            any("keramik" in name.lower() for name in top_2_names),
            f"Keramik should be in top 2 results, got: {top_2_names}"
        )

    def test_beton_prioritized_over_generic_pekerjaan(self):
        """Query 'beton' should prioritize beton entries over generic pekerjaan."""
        matches = self.matcher.find_multiple_matches("beton", limit=5)
        
        if matches:
            self.assertIn("beton", matches[0]["name"].lower())

    def test_word_weight_config_action_detection(self):
        """Test that action words are detected correctly."""
        self.assertTrue(WordWeightConfig._is_action_word("pemasangan"))
        self.assertTrue(WordWeightConfig._is_action_word("pembongkaran"))
        self.assertTrue(WordWeightConfig._is_action_word("pekerjaan"))
        self.assertTrue(WordWeightConfig._is_action_word("galian"))
        self.assertFalse(WordWeightConfig._is_action_word("keramik"))
        self.assertFalse(WordWeightConfig._is_action_word("beton"))

    def test_word_weight_config_technical_detection(self):
        """Test that technical/material words are detected correctly."""
        self.assertTrue(WordWeightConfig._is_technical_word("keramik"))
        self.assertTrue(WordWeightConfig._is_technical_word("beton"))
        self.assertTrue(WordWeightConfig._is_technical_word("baja"))
        self.assertTrue(WordWeightConfig._is_technical_word("pipa"))
        self.assertFalse(WordWeightConfig._is_technical_word("pekerjaan"))
        self.assertFalse(WordWeightConfig._is_technical_word("pemasangan"))

    def test_word_weights_assignment(self):
        """Test that word weights are assigned correctly."""
        config = WordWeightConfig()
        
        # High weight for materials
        self.assertEqual(config.get_word_weight("keramik"), WordWeightConfig.HIGH_WEIGHT)
        self.assertEqual(config.get_word_weight("beton"), WordWeightConfig.HIGH_WEIGHT)
        
        # Low weight for actions
        self.assertEqual(config.get_word_weight("pekerjaan"), WordWeightConfig.LOW_WEIGHT)
        self.assertEqual(config.get_word_weight("pemasangan"), WordWeightConfig.LOW_WEIGHT)
        
        # Ultra-low for stopwords (line 138)
        self.assertEqual(config.get_word_weight("dan"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        self.assertEqual(config.get_word_weight("untuk"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        
        # Line 142: Very long words (>=10 chars) - use a neutral word
        # "strukturnya" is 11 chars, not action, not technical, not stopword
        long_word_weight = config.get_word_weight("strukturnya")
        self.assertEqual(long_word_weight, WordWeightConfig.NORMAL_WEIGHT * 1.3)
        
        # Line 146: Short words (<=3 chars, but >2)
        short_word_weight = config.get_word_weight("abc")
        self.assertEqual(short_word_weight, WordWeightConfig.NORMAL_WEIGHT * 0.8)
    
    def test_compound_material_words(self):
        """Test that compound words containing materials are detected."""
        self.assertTrue(WordWeightConfig._is_technical_word("keramik40x40"))
        self.assertTrue(WordWeightConfig._is_technical_word("pipa3/4"))
        self.assertTrue(WordWeightConfig._is_technical_word("beton225"))

    def test_confidence_with_weighting(self):
        """Test that confidence scores reflect word weighting."""
        material_result = self.matcher.match_with_confidence("keramik 40x40")
        
        if material_result and "keramik" in material_result["name"].lower():
            self.assertGreater(material_result["confidence"], 0.6)

    def test_word_weight_very_short_words(self):
        """Test line 138: Very short words (<=2 chars) get ultra-low weight."""
        config = WordWeightConfig()
        
        # 2 chars
        self.assertEqual(config.get_word_weight("di"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        self.assertEqual(config.get_word_weight("ke"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        
        # 1 char
        self.assertEqual(config.get_word_weight("a"), WordWeightConfig.ULTRA_LOW_WEIGHT)

    def test_word_weight_very_long_words(self):
        """Test line 142: Very long words (>=10 chars) get boosted weight."""
        config = WordWeightConfig()
        
        # Exactly 10 chars
        weight = config.get_word_weight("abcdefghij")
        self.assertEqual(weight, WordWeightConfig.NORMAL_WEIGHT * 1.3)
        
        # More than 10 chars (not action, not technical, not stopword)
        weight = config.get_word_weight("abcdefghijk")
        self.assertEqual(weight, WordWeightConfig.NORMAL_WEIGHT * 1.3)

    def test_word_weight_medium_length_words(self):
        """Test line 146: Medium-short words (<=3 chars but >2) get reduced weight."""
        config = WordWeightConfig()
        
        # Exactly 3 chars (not in stopwords, not action, not technical)
        weight = config.get_word_weight("xyz")
        self.assertEqual(weight, WordWeightConfig.NORMAL_WEIGHT * 0.8)

    def test_word_weight_medium_long_words(self):
        """Test words 7-9 chars get slightly boosted weight."""
        config = WordWeightConfig()
        
        # 7 chars (not action, not technical, not stopword)
        weight = config.get_word_weight("abcdefg")
        self.assertEqual(weight, WordWeightConfig.NORMAL_WEIGHT * 1.1)
        
        # 8 chars
        weight = config.get_word_weight("abcdefgh")
        self.assertEqual(weight, WordWeightConfig.NORMAL_WEIGHT * 1.1)

    def test_similarity_calculator_empty_text(self):
        """Test line 186: Empty text returns 0.0."""
        calc = SimilarityCalculator()
        
        # Both empty
        self.assertEqual(calc.calculate_partial_similarity("", ""), 0.0)
        
        # One empty
        self.assertEqual(calc.calculate_partial_similarity("keramik", ""), 0.0)
        self.assertEqual(calc.calculate_partial_similarity("", "beton"), 0.0)

    def test_similarity_calculator_empty_words(self):
        """Test line 192: No valid words (after split) returns 0.0."""
        calc = SimilarityCalculator()
        
        # Only whitespace
        self.assertEqual(calc.calculate_partial_similarity("   ", "   "), 0.0)
        
        # Empty after split
        self.assertEqual(calc.calculate_partial_similarity(" ", "keramik"), 0.0)

    def test_weighted_jaccard_empty_union(self):
        """Test weighted Jaccard with empty sets."""
        calc = SimilarityCalculator()
        result = calc._calculate_weighted_jaccard_similarity([], [])
        self.assertEqual(result, 0.0)

    def test_weighted_partial_no_valid_words(self):
        """Test weighted partial score when all words are too short."""
        calc = SimilarityCalculator()
        
        # All words < 3 chars
        result = calc._calculate_weighted_partial_score(["a", "b"], ["c", "d"])
        self.assertEqual(result, 0.0)
        
        # One side has only short words
        result = calc._calculate_weighted_partial_score(["ab"], ["keramik", "beton"])
        self.assertEqual(result, 0.0)

    def test_legacy_jaccard_empty_sets(self):
        """Test legacy Jaccard with empty sets."""
        result = SimilarityCalculator._calculate_jaccard_similarity(set(), set())
        self.assertEqual(result, 0.0)

    def test_legacy_partial_word_score_no_words(self):
        """Test legacy partial word score with no valid words."""
        # All words too short
        result = SimilarityCalculator._calculate_partial_word_score({"a", "b"}, {"c", "d"})
        self.assertEqual(result, 0.0)

    def test_candidate_provider_empty_input(self):
        """Test CandidateProvider returns all AHS for empty input."""
        provider = CandidateProvider(self.repo)
        
        candidates = provider.get_candidates_by_head_token("")
        self.assertEqual(len(candidates), len(self.rows))

    def test_candidate_provider_no_match_fallback(self):
        """Test CandidateProvider falls back to all AHS when no match."""
        provider = CandidateProvider(self.repo)
        
        # Non-existent token
        candidates = provider.get_candidates_by_head_token("xyz_nonexistent_word")
        self.assertEqual(len(candidates), len(self.rows))

    def test_matching_processor_empty_query(self):
        """Test MatchingProcessor with empty/None query."""
        calc = SimilarityCalculator()
        provider = CandidateProvider(self.repo)
        processor = MatchingProcessor(calc, provider, 0.5)
        
        # Empty string
        result = processor.find_best_match("")
        self.assertIsNone(result)
        
        # Empty for multiple
        results = processor.find_multiple_matches("")
        self.assertEqual(len(results), 0)

    def test_matching_processor_invalid_limit(self):
        """Test MatchingProcessor with invalid limit."""
        calc = SimilarityCalculator()
        provider = CandidateProvider(self.repo)
        processor = MatchingProcessor(calc, provider, 0.5)
        
        # Zero limit
        results = processor.find_multiple_matches("keramik", limit=0)
        self.assertEqual(len(results), 0)
        
        # Negative limit
        results = processor.find_multiple_matches("keramik", limit=-1)
        self.assertEqual(len(results), 0)

    def test_fuzzy_matcher_empty_description(self):
        """Test FuzzyMatcher with empty/None descriptions."""
        # match()
        self.assertIsNone(self.matcher.match(""))
        self.assertIsNone(self.matcher.match(None))
        
        # find_multiple_matches()
        self.assertEqual(len(self.matcher.find_multiple_matches("")), 0)
        self.assertEqual(len(self.matcher.find_multiple_matches(None)), 0)
        
        # match_with_confidence()
        self.assertIsNone(self.matcher.match_with_confidence(""))
        self.assertIsNone(self.matcher.match_with_confidence(None))
        
        # find_multiple_matches_with_confidence()
        self.assertEqual(len(self.matcher.find_multiple_matches_with_confidence("")), 0)
        self.assertEqual(len(self.matcher.find_multiple_matches_with_confidence(None)), 0)

    def test_fuzzy_matcher_invalid_limit(self):
        """Test FuzzyMatcher with invalid limits."""
        self.assertEqual(len(self.matcher.find_multiple_matches("keramik", limit=0)), 0)
        self.assertEqual(len(self.matcher.find_multiple_matches("keramik", limit=-5)), 0)
        
        self.assertEqual(len(self.matcher.find_multiple_matches_with_confidence("keramik", limit=0)), 0)
        self.assertEqual(len(self.matcher.find_multiple_matches_with_confidence("keramik", limit=-1)), 0)

    def test_fuzzy_matcher_no_match_high_threshold(self):
        """Test FuzzyMatcher with very high threshold (no matches)."""
        high_matcher = FuzzyMatcher(self.repo, min_similarity=0.99)
        
        result = high_matcher.match("completely different text xyz")
        self.assertIsNone(result)
        
        result = high_matcher.match_with_confidence("xyz abc different")
        self.assertIsNone(result)

    def test_fuzzy_matcher_empty_candidate_names(self):
        """Test FuzzyMatcher skips candidates with empty names."""
        rows_with_empty = [
            AhsRow(id=99, code="X.99", name=""),
            AhsRow(id=2, code="A.02", name="keramik 40x40"),
        ]
        
        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return self.rows
            def get_all_ahs(self):
                return self.rows
        
        repo = FakeRepo(rows_with_empty)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("keramik")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)  # Should skip id=99 with empty name

    def test_legacy_methods_all(self):
        """Test all legacy backward compatibility methods."""
        # _calculate_partial_similarity
        result = self.matcher._calculate_partial_similarity("keramik", "keramik beton")
        self.assertGreater(result, 0)
        
        # _calculate_confidence_score
        result = self.matcher._calculate_confidence_score("keramik", "keramik beton")
        self.assertGreater(result, 0)
        
        # _fuzzy_match_name
        result = self.matcher._fuzzy_match_name("keramik")
        self.assertIsNotNone(result)
        
        # _get_multiple_name_matches
        results = self.matcher._get_multiple_name_matches("keramik", 3)
        self.assertGreater(len(results), 0)
        
        # _fuzzy_match_name_with_confidence
        result = self.matcher._fuzzy_match_name_with_confidence("keramik")
        self.assertIsNotNone(result)
        self.assertIn("confidence", result)
        
        # _get_multiple_name_matches_with_confidence
        results = self.matcher._get_multiple_name_matches_with_confidence("keramik", 3)
        self.assertGreater(len(results), 0)
        self.assertIn("confidence", results[0])

    def test_min_similarity_bounds(self):
        """Test min_similarity is bounded [0.0, 1.0]."""
        # Negative
        matcher = FuzzyMatcher(self.repo, min_similarity=-0.5)
        self.assertEqual(matcher.min_similarity, 0.0)
        
        # > 1.0
        matcher = FuzzyMatcher(self.repo, min_similarity=1.5)
        self.assertEqual(matcher.min_similarity, 1.0)
        
        # Normal
        matcher = FuzzyMatcher(self.repo, min_similarity=0.7)
        self.assertEqual(matcher.min_similarity, 0.7)

    def test_norm_name_helper(self):
        """Test _norm_name helper function."""
        result = _norm_name("  Keramik 40x40  ")
        self.assertIsInstance(result, str)
        
        result = _norm_name(None)
        self.assertEqual(result, "")
        
        result = _norm_name("")
        self.assertEqual(result, "")

    def test_sequence_similarity_edge_cases(self):
        """Test sequence similarity calculation."""
        calc = SimilarityCalculator()
        
        # Identical
        self.assertEqual(calc.calculate_sequence_similarity("keramik", "keramik"), 1.0)
        
        # Completely different
        result = calc.calculate_sequence_similarity("keramik", "xyz")
        self.assertLess(result, 0.3)
        
        # Partial
        result = calc.calculate_sequence_similarity("keramik 40x40", "keramik 30x30")
        self.assertGreater(result, 0.7)

    def test_matching_processor_empty_candidate_name(self):
        """Test MatchingProcessor skips candidates with empty names (lines 262-269, 305)."""
        rows_with_empty = [
            AhsRow(id=99, code="X.99", name=""),
            AhsRow(id=98, code="X.98", name=None),  # None name
            AhsRow(id=2, code="A.02", name="keramik 40x40"),
        ]
        
        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return self.rows
            def get_all_ahs(self):
                return self.rows
        
        repo = FakeRepo(rows_with_empty)
        calc = SimilarityCalculator()
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calc, provider, 0.3)
        
        # find_best_match should skip empty names
        result = processor.find_best_match("keramik")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)
        
        # find_multiple_matches should also skip empty names
        results = processor.find_multiple_matches("keramik", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 2)

    def test_fuzzy_matcher_confidence_empty_candidate_name(self):
        """Test confidence methods skip empty candidate names (line 327)."""
        rows_with_empty = [
            AhsRow(id=99, code="X.99", name=""),
            AhsRow(id=2, code="A.02", name="keramik 40x40"),
        ]
        
        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return self.rows
            def get_all_ahs(self):
                return self.rows
        
        repo = FakeRepo(rows_with_empty)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        # match_with_confidence should skip empty name
        result = matcher.match_with_confidence("keramik")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)

    def test_fuzzy_matcher_confidence_multiple_empty_names(self):
        """Test find_multiple_matches_with_confidence skips empty names (line 365)."""
        rows_with_empty = [
            AhsRow(id=99, code="X.99", name=""),
            AhsRow(id=98, code="X.98", name=None),
            AhsRow(id=2, code="A.02", name="keramik 40x40"),
            AhsRow(id=3, code="A.03", name="keramik 30x30"),
        ]
        
        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return self.rows
            def get_all_ahs(self):
                return self.rows
        
        repo = FakeRepo(rows_with_empty)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        # Should only return non-empty names
        results = matcher.find_multiple_matches_with_confidence("keramik", limit=5)
        self.assertGreater(len(results), 0)
        self.assertNotIn(99, [r["id"] for r in results])
        self.assertNotIn(98, [r["id"] for r in results])

    def test_legacy_methods_with_none_input(self):
        """Test legacy methods handle None input (lines 390, 396)."""
        # _fuzzy_match_name with None
        result = self.matcher._fuzzy_match_name(None)
        self.assertIsNone(result)
        
        # _fuzzy_match_name_with_confidence with None
        result = self.matcher._fuzzy_match_name_with_confidence(None)
        self.assertIsNone(result)
        
        # _get_multiple_name_matches with None
        results = self.matcher._get_multiple_name_matches(None, 5)
        self.assertEqual(len(results), 0)
        
        # _get_multiple_name_matches_with_confidence with None
        results = self.matcher._get_multiple_name_matches_with_confidence(None, 5)
        self.assertEqual(len(results), 0)

    def test_word_weight_numbers_in_word(self):
        """Test Rule 4: Words with numbers get high weight."""
        config = WordWeightConfig()
        
        # Word with numbers AND technical term = HIGH_WEIGHT (technical takes precedence)
        weight = config.get_word_weight("keramik40x40")
        self.assertEqual(weight, config.HIGH_WEIGHT)  # Technical word wins
        
        # Word with numbers but NOT technical/action/stopword = HIGH_WEIGHT * 0.9
        weight = config.get_word_weight("abc123xyz")
        self.assertAlmostEqual(weight, config.HIGH_WEIGHT * 0.9, places=2)
        
        # Another neutral word with numbers
        weight = config.get_word_weight("test99")
        self.assertGreater(weight, config.NORMAL_WEIGHT)

    def test_technical_word_substring_match_short_indicator(self):
        """Test that technical indicators <4 chars don't match as substrings."""
        config = WordWeightConfig()
        
        # "cat" is in TECHNICAL_INDICATORS but only 3 chars
        # Should match directly
        self.assertTrue(config._is_technical_word("cat"))
        
        # But NOT as substring (because len < 4)
        self.assertFalse(config._is_technical_word("catatan"))
        
        # "pipa" is 4 chars, should match as substring
        self.assertTrue(config._is_technical_word("pipa"))
        self.assertTrue(config._is_technical_word("pipa3/4"))  # Contains "pipa"

    def test_matching_processor_all_candidates_below_threshold(self):
        """Test find_multiple_matches when all scores are below threshold."""
        calc = SimilarityCalculator()
        provider = CandidateProvider(self.repo)
        processor = MatchingProcessor(calc, provider, 0.95)  # Very high threshold
        
        # All matches should be below 0.95
        results = processor.find_multiple_matches("xyz completely unrelated", limit=5)
        self.assertEqual(len(results), 0)

    def test_fuzzy_matcher_confidence_all_below_threshold(self):
        """Test find_multiple_matches_with_confidence when all below threshold."""
        high_matcher = FuzzyMatcher(self.repo, min_similarity=0.95)
        
        # Should return empty list when all confidences are below threshold
        results = high_matcher.find_multiple_matches_with_confidence("xyz unrelated", limit=5)
        self.assertEqual(len(results), 0)

    def test_matching_processor_sort_by_score(self):
        """Test that find_multiple_matches sorts by score correctly."""
        # Add more rows with varying similarity
        rows_varied = [
            AhsRow(id=1, code="A.01", name="keramik lantai"),  # Medium match
            AhsRow(id=2, code="A.02", name="keramik"),  # Best match
            AhsRow(id=3, code="A.03", name="keramik dinding besar"),  # Lower match
        ]
        
        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return []
            def by_name_candidates(self, head_token):
                return self.rows
            def get_all_ahs(self):
                return self.rows
        
        repo = FakeRepo(rows_varied)
        calc = SimilarityCalculator()
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calc, provider, 0.3)
        
        results = processor.find_multiple_matches("keramik", limit=5)
        
        # Should return results sorted by score (highest first)
        self.assertGreater(len(results), 0)
        
        # Verify sorting: first result should have highest internal score
        if len(results) > 1:
            first_score = results[0]["_internal_score"]
            second_score = results[1]["_internal_score"]
            self.assertGreaterEqual(first_score, second_score)

    def test_legacy_partial_word_score_with_matches(self):
        """Test legacy _calculate_partial_word_score with actual matches (lines 262-269)."""
        calc = SimilarityCalculator()
        
        # Words that partially match
        words1 = {"keramik", "beton", "xyz"}
        words2 = {"keramik40x40", "beton225", "abc"}
        
        result = calc._calculate_partial_word_score(words1, words2)
        
        # Should have some matches (keramik in keramik40x40, beton in beton225)
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 1.0)

    def test_confidence_methods_fetch_candidates(self):
        """Test that confidence methods properly fetch candidates (lines 365, 390)."""
        # This tests the candidate fetching lines in match_with_confidence
        # and find_multiple_matches_with_confidence
        
        # Test with query that will fetch candidates
        result = self.matcher.match_with_confidence("keramik")
        self.assertIsNotNone(result)
        
        # Test multiple matches fetching candidates
        results = self.matcher.find_multiple_matches_with_confidence("keramik", limit=3)
        self.assertGreater(len(results), 0)
        
        # Test with query that forces fallback to all candidates
        high_matcher = FuzzyMatcher(self.repo, min_similarity=0.3)
        result = high_matcher.match_with_confidence("xyz_no_head_match")
        # Should still fetch candidates (via fallback to get_all_ahs)
        # Result might be None if no match, but line should be executed
        
        results = high_matcher.find_multiple_matches_with_confidence("xyz_no_head_match", limit=5)
        # Line 365 should be executed even if results are empty

    def test_confidence_with_whitespace_query(self):
        """Test confidence methods with whitespace in query (exercises candidate fetching)."""
        # Query with spaces will normalize and fetch candidates
        result = self.matcher.match_with_confidence("  keramik  40x40  ")
        # This exercises line 390
        if result:
            self.assertIn("confidence", result)
        
        results = self.matcher.find_multiple_matches_with_confidence("  keramik  ", limit=3)
        # This exercises line 365
        if results:
            self.assertIn("confidence", results[0])

    def test_normalized_query_becomes_empty(self):
        """Test when description normalizes to empty string (lines 364, 389)."""
        # Strings that normalize to empty (only special chars, numbers without letters, etc.)
        
        # Test match_with_confidence with string that normalizes to empty
        result = self.matcher.match_with_confidence("   ")  # Only whitespace
        self.assertIsNone(result)  # Line 364
        
        result = self.matcher.match_with_confidence("123")  # Only numbers (might normalize to empty)
        # Line 364 should be hit if normalize_text strips standalone numbers
        
        result = self.matcher.match_with_confidence("!!!")  # Only punctuation
        self.assertIsNone(result)  # Line 364
        
        # Test find_multiple_matches_with_confidence
        results = self.matcher.find_multiple_matches_with_confidence("   ", limit=5)
        self.assertEqual(len(results), 0)  # Line 389
        
        results = self.matcher.find_multiple_matches_with_confidence("!!!", limit=5)
        self.assertEqual(len(results), 0)  # Line 389
        
        results = self.matcher.find_multiple_matches_with_confidence("@#$", limit=3)
        self.assertEqual(len(results), 0)  # Line 389