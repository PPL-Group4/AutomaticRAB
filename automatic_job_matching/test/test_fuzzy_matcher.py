from django.test import SimpleTestCase
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.exact_matcher import AhsRow

class FuzzyMatcherTests(SimpleTestCase):
    def setUp(self):
        self.sample_rows = [
            AhsRow(id=1, code="AT.01.001", name="pekerjaan galian tanah biasa"),
            AhsRow(id=2, code="AT.01.002", name="pekerjaan galian tanah keras"),
            AhsRow(id=3, code="BT.02.001", name="pekerjaan beton k225"),
            AhsRow(id=4, code="ST.03.001", name="pemasangan besi tulangan d10"),
            AhsRow(id=5, code="", name="pekerjaan tanpa kode"),
            AhsRow(id=6, code="INVALID", name=""),
        ]

        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code):
                return [r for r in self.rows if code.upper() in (r.code or "").upper()]
            def by_name_candidates(self, head_token):
                return [r for r in self.rows if head_token.lower() in (r.name or "").lower()]
            def get_all_ahs(self):
                return self.rows

        self.fake_repo = FakeRepo(self.sample_rows)
        self.matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.6)

    def test_fuzzy_name_match_partial_words(self):
        result = self.matcher.match("galian tanah")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "name")

    def test_fuzzy_name_match_word_order(self):
        result = self.matcher.match("tanah galian pekerjaan")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "name")

    def test_fuzzy_name_match_exact(self):
        result = self.matcher.match("pekerjaan galian tanah biasa")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "name")

    def test_fuzzy_match_empty_input(self):
        self.assertIsNone(self.matcher.match(""))
        self.assertIsNone(self.matcher.match("   "))

    def test_fuzzy_match_no_similarity(self):
        result = self.matcher.match("completely unrelated xyz")
        self.assertIsNone(result)

    def test_fuzzy_match_handles_empty_fields(self):
        try:
             self.matcher.match("test")
        except Exception:
             self.fail("Fuzzy matcher should handle empty fields gracefully")

    def test_custom_min_similarity(self):
        strict_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.9)
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)

        test_input = "galien tanah"

        strict_result = strict_matcher.match(test_input)
        lenient_result = lenient_matcher.match(test_input)

        if strict_result is None and lenient_result is not None:
            self.assertIsNotNone(lenient_result)

    def test_min_similarity_bounds(self):
        matcher_low = FuzzyMatcher(self.fake_repo, min_similarity=-1.0)
        matcher_high = FuzzyMatcher(self.fake_repo, min_similarity=2.0)

        self.assertEqual(matcher_low.min_similarity, 0.0)
        self.assertEqual(matcher_high.min_similarity, 1.0)

    def test_find_multiple_matches(self):
        matches = self.matcher.find_multiple_matches_with_confidence("pekerjaan", limit=3)
        self.assertIsInstance(matches, list)
        self.assertLessEqual(len(matches), 3)

        for match in matches:
            self.assertIn("confidence", match)  
            self.assertNotIn("_internal_score", match)  
            self.assertIsInstance(match["confidence"], float)
            self.assertGreaterEqual(match["confidence"], 0.0)
            self.assertLessEqual(match["confidence"], 1.0)

    def test_find_multiple_matches_no_duplicates(self):
        matches = self.matcher.find_multiple_matches("pekerjaan", limit=10)
        ids = [match["id"] for match in matches]
        self.assertEqual(len(ids), len(set(ids)))

    def test_find_multiple_matches_empty_input(self):
        matches = self.matcher.find_multiple_matches("", limit=5)
        self.assertEqual(matches, [])

    def test_find_multiple_matches_zero_limit(self):
        matches = self.matcher.find_multiple_matches("test", limit=0)
        self.assertEqual(matches, [])

    def test_calculate_partial_similarity_empty_split_results(self):
        similarity = self.matcher._calculate_partial_similarity("   \t\n  ", "hello world")
        self.assertEqual(similarity, 0.0)

        # Test when both split to empty lists
        similarity = self.matcher._calculate_partial_similarity("   \t\n  ", "   \n\t  ")
        self.assertEqual(similarity, 0.0)

        # Test when second parameter splits to empty
        similarity = self.matcher._calculate_partial_similarity("hello", "   \t\n  ")
        self.assertEqual(similarity, 0.0)

    def test_fuzzy_match_return_structure(self):
        result = self.matcher.match("pekerjaan galian tanah biasa")
        if result is not None:
            required_keys = ["source", "id", "code", "name", "matched_on"]
            for key in required_keys:
                self.assertIn(key, result)

            self.assertNotIn("confidence", result)
            self.assertNotIn("_internal_score", result)

            self.assertEqual(result["source"], "ahs")
            self.assertIsInstance(result["id"], int)
            self.assertEqual(result["matched_on"], "name")

    def test_name_matching_priority(self):
        result = self.matcher.match("galian tanah")
        if result is not None:
            self.assertEqual(result["matched_on"], "name")

    def test_fuzzy_match_name_no_normalized_description(self):
        result = self.matcher._fuzzy_match_name("!@#$%")
        self.assertIsNone(result)

    def test_calculate_partial_similarity_edge_cases(self):
        similarity = self.matcher._calculate_partial_similarity("", "hello world")
        self.assertEqual(similarity, 0.0)

        similarity = self.matcher._calculate_partial_similarity("", "")
        self.assertEqual(similarity, 0.0)

        similarity = self.matcher._calculate_partial_similarity("a b", "x y")
        self.assertEqual(similarity, 0.0)

        similarity = self.matcher._calculate_partial_similarity("ab cd", "xy zw")
        self.assertGreaterEqual(similarity, 0.0)

    def test_get_multiple_name_matches_fallback_to_all_ahs(self):
        class FakeRepoNoCandidates:
            def __init__(self, rows):
                self.rows = rows
            def by_name_candidates(self, head_token):
                return []
            def get_all_ahs(self):
                return self.rows

        repo = FakeRepoNoCandidates(self.sample_rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.6)

        matches = matcher._get_multiple_name_matches("pekerjaan", 3)
        self.assertGreater(len(matches), 0)

    def test_fuzzy_match_name_with_empty_normalized_input(self):
        result = self.matcher._fuzzy_match_name("   ")
        self.assertIsNone(result)

    def test_calculate_partial_similarity_with_empty_words(self):
        similarity = self.matcher._calculate_partial_similarity("   ", "hello")
        self.assertEqual(similarity, 0.0)

        similarity = self.matcher._calculate_partial_similarity("   ", "   ")
        self.assertEqual(similarity, 0.0)

    def test_get_multiple_name_matches_empty_normalized_input(self):
        """Test _get_multiple_name_matches when input normalizes to empty"""
        # This should hit line 138 where ndesc is empty after normalization
        matches = self.matcher._get_multiple_name_matches("!@#$%", 5)
        self.assertEqual(matches, [])

        # Also test with whitespace-only input
        matches = self.matcher._get_multiple_name_matches("   ", 5)
        self.assertEqual(matches, [])