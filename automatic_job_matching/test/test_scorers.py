from django.test import SimpleTestCase
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer, ExactConfidenceScorer, NoOpScorer

class ConfidenceScorerStrategyTests(SimpleTestCase):
    """Unit tests for new scoring strategy classes."""

    def setUp(self):
        from automatic_job_matching.service.scoring import FuzzyConfidenceScorer, ExactConfidenceScorer, NoOpScorer
        self.fuzzy = FuzzyConfidenceScorer()
        self.exact = ExactConfidenceScorer()
        self.noop = NoOpScorer()

    def test_exact_scorer(self):
        self.assertEqual(self.exact.score("abc", "abc"), 1.0)
        self.assertEqual(self.exact.score("abc", "abcd"), 0.0)

    def test_noop_scorer(self):
        self.assertEqual(self.noop.score("anything", "here"), 0.0)

    def test_fuzzy_exact_equivalence(self):
        self.assertGreaterEqual(self.fuzzy.score("pekerjaan galian", "pekerjaan galian"), 0.99)
    
    def test_fuzzy_partial_lower(self):
        exact = self.fuzzy.score("pekerjaan galian tanah", "pekerjaan galian tanah")
        partial = self.fuzzy.score("pekerjaan galian", "pekerjaan galian tanah")
        self.assertGreaterEqual(exact, partial)
        self.assertGreaterEqual(partial, 0.8)  
    
    def test_fuzzy_bounds(self):
        s = self.fuzzy.score("", "abc")
        self.assertEqual(s, 0.0)
        s2 = self.fuzzy.score("abc", "")
        self.assertEqual(s2, 0.0)
        within = self.fuzzy.score("abc", "abc d")
        self.assertGreaterEqual(within, 0.0)
        self.assertLessEqual(within, 1.0)

    def test_multi_word_bonus_increases_score(self):
        """Test that matching 2+ significant words increases score."""
        # Query with 2 significant words that both match
        query = "bongkar batu"
        candidate = "bongkar 1 m3 pasangan batu"
        
        score = self.fuzzy.score(query, candidate)
        
        # Should get multi-word bonus
        # Base score ~0.3-0.4 + 0.20 bonus = ~0.5-0.6
        self.assertGreater(score, 0.45, 
                          f"Expected multi-word bonus, got {score}")
    
    def test_single_word_no_multi_bonus(self):
        """Test that single-word queries don't get multi-word bonus."""
        single_score = self.fuzzy.score("batu", "pasangan batu")
        multi_score = self.fuzzy.score("bongkar batu", "bongkar pasangan batu")
        
        # Multi-word should score higher due to bonus
        self.assertGreater(multi_score, single_score)
    
    def test_only_one_word_matches_no_bonus(self):
        """Test that matching only 1 of 2 words doesn't give bonus."""
        # Only "batu" matches (one significant word)
        one_match = self.fuzzy.score("cat batu", "bongkar pasangan batu")
        
        # Both "bongkar" and "batu" match (should get multi-word bonus)
        both_match = self.fuzzy.score("bongkar batu", "bongkar pasangan batu")
        
        # The difference should be at least the multi-word bonus (~0.20)
        self.assertGreater(both_match - one_match, 0.15)
    
    def test_multi_word_bonus_all_words_required(self):
        """Test that ALL significant words must match for bonus."""
        # Both "bongkar" and "batu" match
        both_match = self.fuzzy.score("bongkar batu", "bongkar 1 m3 batu")
        
        # Only "batu" matches
        one_match = self.fuzzy.score("keramik batu", "bongkar 1 m3 batu")
        
        # Both-match should score significantly higher
        self.assertGreater(both_match, one_match + 0.15)
    
    def test_short_words_ignored_in_bonus(self):
        """Test that short words (<4 chars) don't count for bonus."""
        # "dan" is only 3 chars, should be ignored
        score = self.fuzzy.score("bongkar dan batu", "bongkar pasangan batu")
        
        # Should still get bonus for "bongkar" and "batu"
        self.assertGreater(score, 0.45)
    
    def test_score_clamped_to_1_0(self):
        """Test that scores never exceed 1.0 even with bonuses."""
        # Very high similarity + bonus should still clamp to 1.0
        score = self.fuzzy.score(
            "pekerjaan galian tanah biasa",
            "pekerjaan galian tanah biasa"
        )
        
        self.assertLessEqual(score, 1.0)
        self.assertGreaterEqual(score, 0.99)  # Should be very close to 1.0
    
    def test_partial_match_ratio_scales_bonus(self):
        """Test that bonus scales with match percentage."""
        # 2/2 words match (100%)
        full_match = self.fuzzy.score("bongkar batu", "bongkar 1 m3 batu")
        
        # 2/3 words match (66%)
        partial_match = self.fuzzy.score("bongkar batu keramik", "bongkar 1 m3 batu")
        
        # Full match should score higher
        self.assertGreater(full_match, partial_match)
    
    def test_empty_strings_no_bonus(self):
        """Test empty strings don't crash multi-word bonus calculation."""
        self.assertEqual(self.fuzzy.score("", ""), 0.0)
        self.assertEqual(self.fuzzy.score("bongkar", ""), 0.0)
        self.assertEqual(self.fuzzy.score("", "bongkar"), 0.0)
    
    def test_high_similarity_bonus_still_applies(self):
        """Test that original high-similarity bonus still works."""
        # Very similar strings should get the 1.05x multiplier bonus
        score = self.fuzzy.score(
            "pemasangan pipa pvc diameter",
            "pemasangan pipa pvc"
        )
        self.assertGreater(score, 0.70)

    def test_bonus_eligible_boundary_conditions(self):
        """Test bonus eligibility at exact threshold boundaries."""
        # Test at exact BONUS_THRESHOLD_SEQ (0.75)
        query = "abc def ghi"
        candidate = "abc def xyz"
        
        score = self.fuzzy.score(query, candidate)
        
        # Should be eligible or very close
        self.assertGreaterEqual(score, 0.5)
    
    def test_multi_word_bonus_with_no_significant_words(self):
        """Test multi-word bonus when query has no significant words (all <4 chars)."""
        # All words < 4 chars (should get 0 bonus)
        score = self.fuzzy.score("a b c", "abc def ghi")
        
        # Should have low score (no significant words = no bonus)
        self.assertLess(score, 0.3)
    
    def test_multi_word_bonus_calculation_edge_cases(self):
        """Test edge cases in multi-word bonus calculation."""
        # Test with exactly 1 significant word (no bonus)
        score = self.fuzzy.score("batu", "pasangan batu merah")
        self.assertLess(score, 0.6)  # No multi-word bonus
        
        # Test with exactly 2 significant words both matching (full bonus)
        score = self.fuzzy.score("bongkar batu", "bongkar 1 m3 batu")
        self.assertGreater(score, 0.55)  # Should get bonus
        
        # Test with 3 significant words, only 1 matches (no bonus)
        score = self.fuzzy.score("bongkar keramik pipa", "pasangan batu belah")
        self.assertLess(score, 0.3)
    
    def test_trivial_check_coverage(self):
        """Test all branches of trivial checking logic."""
        # Both empty
        self.assertEqual(self.fuzzy.score("", ""), 0.0)
        
        # One empty
        self.assertEqual(self.fuzzy.score("abc", ""), 0.0)
        self.assertEqual(self.fuzzy.score("", "abc"), 0.0)
        
        # Identical
        self.assertEqual(self.fuzzy.score("exact", "exact"), 1.0)
        
        # Different (not trivial, goes to main scoring)
        score = self.fuzzy.score("abc", "def")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_multi_word_bonus_edge_case_zero_significant_words(self):
        """Test multi-word bonus with zero significant words."""
        # All words are < 4 chars
        score = self.fuzzy.score("a b c", "abc def ghi jkl")
        
        # Should have low score
        self.assertLess(score, 0.3)
    
    def test_multi_word_bonus_exactly_one_significant_word(self):
        """Test that exactly 1 significant word doesn't trigger bonus."""
        # Only "batu" is significant (>= 4 chars)
        score = self.fuzzy.score("cat batu", "pasangan batu merah")
        
        # Should not get multi-word bonus
        self.assertLess(score, 0.6)
    
    def test_multi_word_bonus_with_partial_match_ratio(self):
        """Test that bonus scales with match ratio."""
        # 2 out of 4 significant words match (50%)
        score_50 = self.fuzzy.score("bongkar keramik pipa listrik", "bongkar pasangan batu merah")
        
        # 4 out of 4 significant words match (100%)
        score_100 = self.fuzzy.score("bongkar pasangan batu merah", "bongkar pasangan batu merah")
        
        # 100% match should score significantly higher
        self.assertGreater(score_100, score_50 + 0.15)
    
    def test_overlap_calculation_handles_empty_sets(self):
        """Test overlap calculations with empty token sets."""
        # Empty vs non-empty
        score = self.fuzzy.score("", "abc def")
        self.assertEqual(score, 0.0)
        
        score = self.fuzzy.score("abc", "")
        self.assertEqual(score, 0.0)
        
        # Both empty
        score = self.fuzzy.score("", "")
        self.assertEqual(score, 0.0)
        
        # Whitespace only
        score = self.fuzzy.score("   ", "abc")
        self.assertEqual(score, 0.0)
    
    def test_bonus_eligibility_threshold_checking(self):
        """Test bonus eligibility at similarity thresholds."""
        # High sequence + high jaccard (should get bonus)
        query = "pekerjaan galian tanah"
        candidate = "pekerjaan galian tanah biasa"
        score = self.fuzzy.score(query, candidate)
        
        # Should be high score (bonus applied)
        self.assertGreater(score, 0.75)
    
    def test_score_clamping_mechanisms(self):
        """Test that score clamping works for all edge cases."""
        # Test exact match (should return 1.0, clamped)
        score = self.fuzzy.score("exact match", "exact match")
        self.assertEqual(score, 1.0)
        
        # Test no match (should be >= 0.0, clamped)
        score = self.fuzzy.score("xyz", "abc")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        
        # Test partial match (should be in valid range)
        score = self.fuzzy.score("galian tanah", "pekerjaan galian tanah biasa")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)
    
    def test_scoring_handles_edge_cases_gracefully(self):
        """Test that scoring handles various edge cases."""
        # Empty strings
        self.assertEqual(self.fuzzy.score("", ""), 0.0)
        self.assertEqual(self.fuzzy.score("abc", ""), 0.0)
        
        # Identical strings
        self.assertEqual(self.fuzzy.score("exact", "exact"), 1.0)
        
        # Completely different
        score = self.fuzzy.score("xyz", "abc")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_score_boundaries_never_violated(self):
        """Test that scores are properly bounded to [0, 1] range."""
        test_cases = [
            ("", "test"),                              # Empty case
            ("identical", "identical"),                # Perfect match
            ("galian tanah", "pekerjaan galian tanah"), # Partial match
            ("xyz", "abc"),                            # No match
        ]
        
        for query, candidate in test_cases:
            score = self.fuzzy.score(query, candidate)
            self.assertGreaterEqual(score, 0.0, f"Score below 0 for: {query} vs {candidate}")
            self.assertLessEqual(score, 1.0, f"Score above 1 for: {query} vs {candidate}")
    
    def test_bonus_calculations_are_applied_correctly(self):
        """Test that bonuses are calculated and applied properly."""
        # High similarity should get bonus
        high_sim = self.fuzzy.score("galian tanah", "pekerjaan galian tanah biasa")
        self.assertGreater(high_sim, 0.5)
        
        # Multi-word matches should get bonus
        multi_word = self.fuzzy.score("bongkar batu", "bongkar 1 m3 batu")
        self.assertGreater(multi_word, 0.45)
        
        # Low similarity should not get bonus
        low_sim = self.fuzzy.score("xyz", "abc def")
        self.assertLess(low_sim, 0.3)
    
    def test_significant_word_detection_for_bonuses(self):
        """Test that significant words are properly identified for bonuses."""
        # Query with 2+ significant words (>=4 chars)
        significant = self.fuzzy.score("bongkar batu", "bongkar pasangan batu")
        
        # Query with short words (<4 chars)
        short_words = self.fuzzy.score("abc def", "abc def ghi")
        
        # Significant words should produce higher scores
        self.assertGreater(significant, 0.4)
    
    def test_overlap_metrics_with_various_inputs(self):
        """Test overlap metric calculations with various input combinations."""
        # Normal case
        score = self.fuzzy.score("galian tanah", "pekerjaan galian tanah")
        self.assertGreater(score, 0.5)
        
        # Edge case: one set empty after tokenization
        score = self.fuzzy.score("   ", "test")
        self.assertEqual(score, 0.0)
        
        # Edge case: both empty
        score = self.fuzzy.score("", "")
        self.assertEqual(score, 0.0)
    
    def test_perfect_matches_always_return_maximum_score(self):
        """Test that identical strings always get perfect score."""
        test_strings = [
            "pekerjaan galian tanah",
            "bongkar pasangan batu",
            "pemasangan keramik",
        ]
        
        for text in test_strings:
            score = self.fuzzy.score(text, text)
            self.assertEqual(score, 1.0, f"Identical strings should score 1.0: {text}")
    
    def test_partial_matches_return_intermediate_scores(self):
        """Test that partial matches return reasonable intermediate scores."""
        # Partial overlap should be between 0 and 1
        score = self.fuzzy.score("galian tanah", "pekerjaan galian tanah biasa")
        
        self.assertGreater(score, 0.0, "Partial match should have positive score")
        self.assertLess(score, 1.0, "Partial match shouldn't be perfect")
        self.assertGreater(score, 0.4, "Good partial match should score reasonably high")
    
    def test_high_quality_matches_receive_appropriate_bonuses(self):
        """Test that high-quality matches receive appropriate bonuses."""
        # Multi-word match with significant overlap
        high_quality = self.fuzzy.score("bongkar batu", "bongkar 1 m3 batu")
        
        # Single word match
        single_word = self.fuzzy.score("batu", "batu belah")
        
        # Multi-word should score higher due to bonus
        self.assertGreater(high_quality, 0.45, "Multi-word matches should get bonuses")
    
    def test_poor_matches_dont_receive_bonuses(self):
        """Test that poor matches don't get bonus boosts."""
        # Very different strings
        poor_match = self.fuzzy.score("xyz", "abc def")
        
        # Should have low score without bonuses
        self.assertLess(poor_match, 0.3, "Poor matches shouldn't receive bonuses")

    def test_overlap_metrics_with_empty_union(self):
        """Test line 110: overlap metrics when union is empty."""
        # Create a scorer to access the _overlap_metrics method
        scorer = FuzzyConfidenceScorer()
        
        # Empty token lists should result in empty union
        jaccard, coverage = scorer._overlap_metrics([], [])
        
        self.assertEqual(jaccard, 0.0)
        self.assertEqual(coverage, 0.0)

    def test_clamp_negative_values(self):
        """Test line 181: clamping negative values to 0.0."""
        scorer = FuzzyConfidenceScorer()
        
        # Test negative value gets clamped to 0.0
        result = scorer._clamp(-0.5)
        self.assertEqual(result, 0.0)
        
        result = scorer._clamp(-1.0)
        self.assertEqual(result, 0.0)
        
        result = scorer._clamp(-0.001)
        self.assertEqual(result, 0.0)

    def test_clamp_values_above_one(self):
        """Test line 183: clamping values > 1.0 to 1.0."""
        scorer = FuzzyConfidenceScorer()
        
        # Test values above 1.0 get clamped to 1.0
        result = scorer._clamp(1.5)
        self.assertEqual(result, 1.0)
        
        result = scorer._clamp(2.0)
        self.assertEqual(result, 1.0)
        
        result = scorer._clamp(1.001)
        self.assertEqual(result, 1.0)

    def test_clamp_valid_range_values(self):
        """Test that clamping doesn't modify values already in [0, 1]."""
        scorer = FuzzyConfidenceScorer()
        
        # Test valid values remain unchanged
        self.assertEqual(scorer._clamp(0.0), 0.0)
        self.assertEqual(scorer._clamp(0.5), 0.5)
        self.assertEqual(scorer._clamp(1.0), 1.0)
        self.assertEqual(scorer._clamp(0.75), 0.75)

    def test_exact_scorer_with_empty_strings(self):
        """Test line 194: ExactConfidenceScorer returns 0.0 for empty strings."""
        scorer = ExactConfidenceScorer()
        
        # Empty query
        self.assertEqual(scorer.score("", "candidate"), 0.0)
        
        # Empty candidate
        self.assertEqual(scorer.score("query", ""), 0.0)
        
        # Both empty
        self.assertEqual(scorer.score("", ""), 0.0)
        
        # Whitespace (should normalize to empty)
        self.assertEqual(scorer.score("   ", "test"), 0.0)
        self.assertEqual(scorer.score("test", "   "), 0.0)

    def test_fuzzy_scorer_with_empty_union_edge_case(self):
        """Test that overlap metrics handle empty union gracefully."""
        scorer = FuzzyConfidenceScorer()
        
        # This should trigger the empty union check
        jaccard, coverage = scorer._overlap_metrics([], [])
        
        self.assertEqual(jaccard, 0.0, "Jaccard should be 0.0 for empty union")
        self.assertEqual(coverage, 0.0, "Coverage should be 0.0 for empty union")

    def test_score_computation_with_extreme_bonus(self):
        """Test that score clamping works when bonuses push score > 1.0."""
        scorer = FuzzyConfidenceScorer()
        
        # Create a scenario where base score + bonuses might exceed 1.0
        # Use identical strings which should give very high base score
        score = scorer.score("pekerjaan galian tanah biasa", "pekerjaan galian tanah biasa")
        
        # Score should be clamped to exactly 1.0
        self.assertEqual(score, 1.0)
        self.assertLessEqual(score, 1.0, "Score should never exceed 1.0 even with bonuses")

    def test_negative_score_impossible_but_clamped(self):
        """Test that negative scores (theoretically impossible) get clamped."""
        scorer = FuzzyConfidenceScorer()
        
        # Test the _clamp method directly with impossible negative value
        clamped = scorer._clamp(-0.1)
        self.assertEqual(clamped, 0.0)
        
        # Normal scoring should never produce negative, but verify it's non-negative
        score = scorer.score("xyz", "abc")
        self.assertGreaterEqual(score, 0.0)

    def test_exact_scorer_comprehensive_empty_input_coverage(self):
        """Comprehensive test for ExactConfidenceScorer empty input handling."""
        scorer = ExactConfidenceScorer()
        
        # All combinations of empty/non-empty
        test_cases = [
            ("", "", 0.0),           # Both empty
            ("", "text", 0.0),       # Empty query
            ("text", "", 0.0),       # Empty candidate
            ("same", "same", 1.0),   # Exact match
            ("different", "text", 0.0),  # No match
        ]
        
        for query, candidate, expected in test_cases:
            result = scorer.score(query, candidate)
            self.assertEqual(result, expected, 
                        f"Failed for query='{query}', candidate='{candidate}'")

    def test_overlap_metrics_direct_empty_union_path(self):
        """Directly test the empty union early return path."""
        scorer = FuzzyConfidenceScorer()
        
        # Call _overlap_metrics with empty token lists
        q_tokens = []
        c_tokens = []
        
        jaccard, coverage = scorer._overlap_metrics(q_tokens, c_tokens)
        
        # Both should be 0.0 when union is empty
        self.assertEqual(jaccard, 0.0)
        self.assertEqual(coverage, 0.0)

    def test_clamp_boundary_values(self):
        """Test clamping at exact boundary values."""
        scorer = FuzzyConfidenceScorer()
        
        # Test exact boundaries
        self.assertEqual(scorer._clamp(0.0), 0.0)
        self.assertEqual(scorer._clamp(1.0), 1.0)
        
        # Test just below 0
        self.assertEqual(scorer._clamp(-0.0001), 0.0)
        
        # Test just above 1
        self.assertEqual(scorer._clamp(1.0001), 1.0)
        
        # Test extreme values
        self.assertEqual(scorer._clamp(-999.0), 0.0)
        self.assertEqual(scorer._clamp(999.0), 1.0)

    def test_exact_scorer_none_inputs(self):
        """Test ExactConfidenceScorer with None inputs."""
        scorer = ExactConfidenceScorer()
        
        # None inputs should be treated as falsy and return 0.0
        self.assertEqual(scorer.score(None, "text"), 0.0)
        self.assertEqual(scorer.score("text", None), 0.0)
        self.assertEqual(scorer.score(None, None), 0.0)

    def test_fuzzy_scorer_empty_after_tokenization(self):
        """Test fuzzy scorer when strings become empty after tokenization."""
        scorer = FuzzyConfidenceScorer()
        
        # Empty strings
        score = scorer.score("", "test")
        self.assertEqual(score, 0.0)
        
        score = scorer.score("test", "")
        self.assertEqual(score, 0.0)
        
        score = scorer.score("", "")
        self.assertEqual(score, 0.0)
        
        # Pure whitespace
        score = scorer.score("   ", "test")
        # Whitespace becomes empty string after strip, handled by _check_trivial
        self.assertEqual(score, 0.0)
        
        score = scorer.score("test", "   ")
        self.assertEqual(score, 0.0)
        
        score = scorer.score("   \t\n", "   \r\n")
        self.assertEqual(score, 0.0)

    def test_overlap_metrics_with_non_empty_but_disjoint_sets(self):
        """Test overlap metrics with non-empty but completely disjoint token sets."""
        scorer = FuzzyConfidenceScorer()
        
        # Completely different tokens
        q_tokens = ["xyz"]
        c_tokens = ["abc"]
        
        jaccard, coverage = scorer._overlap_metrics(q_tokens, c_tokens)
        
        # Jaccard should be 0.0 (no intersection)
        self.assertEqual(jaccard, 0.0)
        
        # Coverage should be 0.0 (no common elements)
        self.assertEqual(coverage, 0.0)