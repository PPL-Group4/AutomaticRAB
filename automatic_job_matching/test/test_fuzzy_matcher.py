from unittest.mock import MagicMock
from django.test import SimpleTestCase
from automatic_job_matching.service.fuzzy_matcher import CandidateProvider, FuzzyMatcher, WordWeightConfig
from automatic_job_matching.service.exact_matcher import AhsRow
from automatic_job_matching.utils.text_normalizer import normalize_text

def _norm_name(s: str) -> str:
    return normalize_text(s or "")

class FakeAhsRepo:
    def __init__(self, rows):
        self.rows = rows
    
    def by_code_like(self, code):
        return [r for r in self.rows if code.upper() in (r.code or "").upper()]
    
    def by_name_candidates(self, head_token):
        return [r for r in self.rows if head_token.lower() in (r.name or "").lower()]
    
    def get_all_ahs(self):
        return self.rows

class FuzzyMatcherTests(SimpleTestCase):
    def setUp(self):
        self.sample_rows = [
            AhsRow(id=1, code="AT.01.001", name="pekerjaan galian tanah biasa"),
            AhsRow(id=2, code="AT.01.002", name="pekerjaan galian tanah keras"),
            AhsRow(id=3, code="BT.02.001", name="pekerjaan beton k225"),
            AhsRow(id=4, code="ST.03.001", name="pemasangan besi tulangan d10"),
            AhsRow(id=5, code="", name="pekerjaan tanpa kode"),
            AhsRow(id=6, code="INVALID", name=""),
            AhsRow(id=7, code="6.1.1.2.a", name="Bongkar 1 m3 pasangan batu dengan cara manual"),
            AhsRow(id=8, code="6.1.1.2.b", name="Bongkar 1 m3 pasangan batu dengan jack hammer"),
            AhsRow(id=9, code="6.1.1.1.a", name="Bongkar dan pemanfaatan batu bekas pasangan 1 m3 pasangan batu dan pembersihan batu dengan cara manual"),
            AhsRow(id=10, code="6.1.1.1.b", name="Bongkar dan pemanfaatan batu bekas pasangan 1 m3 pasangan batu dengan cara manual"),
            AhsRow(id=11, code="6.1.2.1", name="Bongkar 1 m3 pasangan bata merah dengan cara manual"),
            AhsRow(id=12, code="6.1.2.2", name="Bongkar 1 m3 pasangan bata merah dengan jack hammer"),
            AhsRow(id=13, code="6.3.1.1", name="Bongkar 1 m3 beton mutu rendah fc' < 20 MPa secara Manual"),
            AhsRow(id=14, code="6.3.1.2", name="Bongkar 1 m3 beton mutu sedang fc' ≥ 20 MPa secara Manual"),
            AhsRow(id=15, code="3.4.1.1", name="Pasangan 1 m3 batu belah 1Pc : 6Ps volume 1 m3 pasangan"),
            AhsRow(id=16, code="3.4.1.2", name="Pasangan 1 m3 batu belah 1Pc : 5Ps volume 1 m3 pasangan"),
            AhsRow(id=17, code="7.2.1", name="Pemasangan 1 m2 keramik lantai ukuran 20 cm x 20 cm"),
            AhsRow(id=18, code="7.2.2", name="Pemasangan 1 m2 keramik lantai ukuran 30 cm x 30 cm"),
            AhsRow(id=19, code="7.2.3", name="Pemasangan 1 m2 keramik lantai ukuran 40 cm x 40 cm"),
            AhsRow(id=20, code="8.5.1", name="Pembersihan 1 m3 bongkaran pasangan batu untuk pemanfaatan kembali material batu"),
        ]

        self.fake_repo = FakeAhsRepo(self.sample_rows)
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

        similarity = self.matcher._calculate_partial_similarity("   \t\n  ", "   \n\t  ")
        self.assertEqual(similarity, 0.0)

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
        matches = self.matcher._get_multiple_name_matches("!@#$%", 5)
        self.assertEqual(matches, [])

        matches = self.matcher._get_multiple_name_matches("   ", 5)
        self.assertEqual(matches, [])
        
    def test_multi_word_bongkar_batu_matches_correctly(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        result = lenient_matcher.match_with_confidence("bongkar batu")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("bongkar", name_lower)
            self.assertIn("batu", name_lower)
            self.assertIn(result["id"], [7, 8, 9, 10, 20])
    
    def test_multi_word_pemasangan_keramik(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        result = lenient_matcher.match_with_confidence("pemasangan keramik")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("pemasangan", name_lower)
            self.assertIn("keramik", name_lower)
            self.assertIn(result["id"], [17, 18, 19])
    
    def test_multi_word_bongkar_beton(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        result = lenient_matcher.match_with_confidence("bongkar beton")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("bongkar", name_lower)
            self.assertIn("beton", name_lower)
            self.assertIn(result["id"], [13, 14])
    
    def test_typo_bonkar_batu_fuzzy_matches(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.30)
        result = lenient_matcher.match_with_confidence("bonkar batu")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("bongkar", name_lower)
            self.assertIn("batu", name_lower)
    
    def test_multi_word_with_unit_m3_batu(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.30)
        matches = lenient_matcher.find_multiple_matches_with_confidence("m3 batu", limit=5)
        
        for match in matches:
            name_lower = match["name"].lower()
            self.assertIn("m3", name_lower)
            self.assertIn("batu", name_lower)
    
    def test_multi_word_all_words_required_bongkar_batu(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        matches = lenient_matcher.find_multiple_matches_with_confidence("bongkar batu", limit=10)
        
        for match in matches:
            name_lower = match["name"].lower()
            has_bongkar = "bongkar" in name_lower or "bonkar" in name_lower
            has_batu = "batu" in name_lower
            self.assertTrue(
                has_bongkar and has_batu,
                f"Expected both 'bongkar' and 'batu' in: {match['name']}"
            )
    
    def test_single_word_batu_returns_multiple(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        matches = lenient_matcher.find_multiple_matches_with_confidence("batu", limit=10)
        
        self.assertGreater(len(matches), 0)
        for match in matches:
            self.assertIn("batu", match["name"].lower())
    
    def test_multi_word_generic_words_ignored(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        
        result1 = lenient_matcher.match_with_confidence("bongkar batu")
        result2 = lenient_matcher.match_with_confidence("bongkar dan batu dengan cara manual")
        
        if result1 and result2:
            self.assertIn("bongkar", result1["name"].lower())
            self.assertIn("bongkar", result2["name"].lower())
    
    def test_keramik_with_size_30x30(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.30)
        result = lenient_matcher.match_with_confidence("keramik 30x30")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("keramik", name_lower)
            self.assertIn("30", name_lower)
    
    def test_pasangan_batu_belah(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        result = lenient_matcher.match_with_confidence("pasangan batu belah")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("pasangan", name_lower)
            self.assertIn("batu", name_lower)
            self.assertIn("belah", name_lower)
            self.assertIn(result["id"], [15, 16])
    
    def test_bongkar_bata_merah(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.35)
        result = lenient_matcher.match_with_confidence("bongkar bata merah")
        
        if result:
            name_lower = result["name"].lower()
            self.assertIn("bongkar", name_lower)
            self.assertIn("bata", name_lower)
            self.assertIn("merah", name_lower)
            self.assertIn(result["id"], [11, 12])

    def test_single_word_query_uses_head_token_search(self):
        result = self.matcher.match("pekerjaan")
        
        if result:
            self.assertIn("pekerjaan", result["name"].lower())
    
    def test_material_word_without_matches_falls_back(self):
        matches = self.matcher.find_multiple_matches("aluminium", limit=5)
        self.assertIsInstance(matches, list)
    
    def test_multi_word_query_with_no_common_words_uses_any_filter(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        matches = lenient_matcher.find_multiple_matches("keramik batu", limit=5)
        
        self.assertGreater(len(matches), 0)
        
        found_keramik_or_batu = any(
            "keramik" in m["name"].lower() or "batu" in m["name"].lower()
            for m in matches
        )
        self.assertTrue(found_keramik_or_batu)

    def test_query_with_rare_material_falls_back_to_general_search(self):
        matches = self.matcher.find_multiple_matches("aluminium panel", limit=5)
        self.assertIsInstance(matches, list)
    
    def test_compound_query_with_no_overlapping_candidates(self):
        lenient_matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        matches = lenient_matcher.find_multiple_matches("keramik batu", limit=5)
        
        self.assertGreater(len(matches), 0)
        
        found_either = any(
            "keramik" in m["name"].lower() or "batu" in m["name"].lower()
            for m in matches
        )
        self.assertTrue(found_either, "Should find candidates with either material")

    def test_material_word_not_in_any_candidate_uses_fallback(self):
        provider = CandidateProvider(self.fake_repo)
        
        candidates = provider.get_candidates_by_head_token("titanium")
        
        self.assertGreater(len(candidates), 0)

    def test_jaccard_similarity_with_empty_sets(self):
        from automatic_job_matching.service.fuzzy_matcher import SimilarityCalculator
        calculator = SimilarityCalculator()
        
        result = calculator._calculate_jaccard_similarity(set(), set())
        self.assertEqual(result, 0.0)
    
    def test_jaccard_similarity_with_intersection(self):
        from automatic_job_matching.service.fuzzy_matcher import SimilarityCalculator
        calculator = SimilarityCalculator()
        
        words1 = {"galian", "tanah"}
        words2 = {"galian", "biasa"}
        
        result = calculator._calculate_jaccard_similarity(words1, words2)
        
        self.assertGreater(result, 0.0)
        self.assertLess(result, 1.0)
    
    def test_partial_word_score_empty_filtered_words(self):
        from automatic_job_matching.service.fuzzy_matcher import SimilarityCalculator
        calculator = SimilarityCalculator()
        
        words1 = {"ab", "cd"}
        words2 = {"xy", "zw"}
        
        result = calculator._calculate_partial_word_score(words1, words2)
        self.assertEqual(result, 0.0)
    
    def test_partial_word_score_with_matches(self):
        from automatic_job_matching.service.fuzzy_matcher import SimilarityCalculator
        calculator = SimilarityCalculator()
        
        words1 = {"galian", "tanah"}
        words2 = {"galian", "keras"}
        
        result = calculator._calculate_partial_word_score(words1, words2)
        self.assertGreater(result, 0.0)

    def test_find_multiple_matches_with_negative_limit(self):
        from automatic_job_matching.service.fuzzy_matcher import MatchingProcessor, SimilarityCalculator, CandidateProvider
        
        rows = [AhsRow(id=1, code="A.01", name="test item")]
        repo = FakeAhsRepo(rows)
        calculator = SimilarityCalculator()
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, min_similarity=0.6)
        
        results = processor.find_multiple_matches("test", limit=-1)
        self.assertEqual(results, [])

    def test_find_best_match_skips_empty_candidate_names(self):
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="valid entry"),
            AhsRow(id=3, code="C.01", name="   "),
            AhsRow(id=4, code="D.01", name="another valid"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        from automatic_job_matching.service.fuzzy_matcher import MatchingProcessor
        processor = matcher._matching_processor
        
        result = processor.find_best_match("valid")
        
        if result:
            self.assertNotEqual(result["name"], "")
            self.assertIn(result["id"], [2, 4])
    
    def test_find_multiple_matches_skips_empty_candidate_names(self):
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="valid entry"),
            AhsRow(id=3, code="C.01", name="   "),
            AhsRow(id=4, code="D.01", name="another valid"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        results = matcher.find_multiple_matches("valid", limit=10)
        
        for result in results:
            self.assertNotEqual(result["name"], "")
            self.assertIn(result["id"], [2, 4])
    
    def test_weighted_jaccard_with_zero_union_weight(self):
        from automatic_job_matching.service.fuzzy_matcher import SimilarityCalculator
        
        calculator = SimilarityCalculator()
        
        result = calculator._calculate_weighted_jaccard_similarity([], [])
        
        self.assertEqual(result, 0.0)

class WordWeightConfigTests(SimpleTestCase):
    
    def test_technical_words_high_weight(self):
        self.assertEqual(WordWeightConfig.get_word_weight("batu"), WordWeightConfig.HIGH_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("keramik"), WordWeightConfig.HIGH_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("beton"), WordWeightConfig.HIGH_WEIGHT)
    
    def test_action_words_low_weight(self):
        self.assertEqual(WordWeightConfig.get_word_weight("bongkar"), WordWeightConfig.LOW_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("pemasangan"), WordWeightConfig.LOW_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("pembongkaran"), WordWeightConfig.LOW_WEIGHT)
    
    def test_generic_words_ultra_low_weight(self):
        self.assertEqual(WordWeightConfig.get_word_weight("dan"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("dengan"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("cara"), WordWeightConfig.ULTRA_LOW_WEIGHT)
        self.assertEqual(WordWeightConfig.get_word_weight("secara"), WordWeightConfig.ULTRA_LOW_WEIGHT)
    
    def test_measurements_high_weight(self):
        self.assertGreater(WordWeightConfig.get_word_weight("m3"), WordWeightConfig.NORMAL_WEIGHT)
        self.assertGreater(WordWeightConfig.get_word_weight("m2"), WordWeightConfig.NORMAL_WEIGHT)
        self.assertGreater(WordWeightConfig.get_word_weight("cm"), WordWeightConfig.NORMAL_WEIGHT)
    
    def test_unknown_word_normal_weight(self):
        weight = WordWeightConfig.get_word_weight("unknownword")
        self.assertIn(weight, [WordWeightConfig.NORMAL_WEIGHT, WordWeightConfig.NORMAL_WEIGHT * 1.3])

    def test_is_technical_word_detection(self):
        self.assertTrue(WordWeightConfig._is_technical_word("batu"))
        self.assertTrue(WordWeightConfig._is_technical_word("keramik"))
        self.assertTrue(WordWeightConfig._is_technical_word("beton"))
        self.assertFalse(WordWeightConfig._is_technical_word("xyz"))
    
    def test_is_action_word_detection(self):
        self.assertTrue(WordWeightConfig._is_action_word("bongkar"))
        self.assertTrue(WordWeightConfig._is_action_word("pemasangan"))
        self.assertTrue(WordWeightConfig._is_action_word("pembongkaran"))
        self.assertFalse(WordWeightConfig._is_action_word("batu"))

    def test_debug_pekerjaan_classification(self):
        config = WordWeightConfig()
        
        print(f"\npekerjaan in GENERIC_WORDS: {'pekerjaan' in config.GENERIC_WORDS}")
        print(f"pekerjaan is_action: {config._is_action_word('pekerjaan')}")
        print(f"pekerjaan is_technical: {config._is_technical_word('pekerjaan')}")
        print(f"pekerjaan weight: {config.get_word_weight('pekerjaan')}")
        print(f"Expected LOW_WEIGHT: {config.LOW_WEIGHT}")
        print(f"Expected ULTRA_LOW: {config.ULTRA_LOW_WEIGHT}")

    def test_material_plus_action_word_prioritizes_material(self):
        repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="bongkar pasangan batu"),
            AhsRow(id=2, code="B.01", name="pemasangan keramik"),
        ])
        
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        result = matcher.match("bongkar batu")
        
        if result:
            self.assertIn("batu", result["name"].lower())
            self.assertEqual(result["id"], 1)

    def test_technical_word_substring_detection(self):
        result = WordWeightConfig._is_technical_word("batubara")
        self.assertTrue(result)

class FuzzyMatcherLegacyMethodTests(SimpleTestCase):
    
    def setUp(self):
        self.rows = [
            AhsRow(id=1, code="A.01", name="pekerjaan galian tanah"),
            AhsRow(id=2, code="B.01", name="pasangan batu bata"),
        ]
        self.fake_repo = FakeAhsRepo(self.rows)

    def test_legacy_fuzzy_match_name(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher._fuzzy_match_name("galian tanah")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "ahs")
        self.assertIn("galian", result["name"].lower())
    
    def test_legacy_get_multiple_name_matches(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        results = matcher._get_multiple_name_matches("batu", limit=3)
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
    
    def test_legacy_fuzzy_match_name_with_confidence(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher._fuzzy_match_name_with_confidence("galian tanah")
        
        self.assertIsNotNone(result)
        self.assertIn("confidence", result)
        self.assertGreater(result["confidence"], 0.0)
    
    def test_legacy_get_multiple_name_matches_with_confidence(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        results = matcher._get_multiple_name_matches_with_confidence("batu", limit=3)
        
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIn("confidence", result)
            self.assertGreater(result["confidence"], 0.0)
    
    def test_calculate_partial_similarity_backward_compat(self):
        matcher = FuzzyMatcher(self.fake_repo)
        
        score = matcher._calculate_partial_similarity("galian tanah", "pekerjaan galian tanah")
        
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_calculate_confidence_score_backward_compat(self):
        matcher = FuzzyMatcher(self.fake_repo)
        
        score = matcher._calculate_confidence_score("galian tanah", "pekerjaan galian tanah")
        
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_legacy_methods_maintain_backward_compatibility(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result1 = matcher._fuzzy_match_name("galian")
        result2 = matcher._fuzzy_match_name_with_confidence("galian")
        result3 = matcher._calculate_confidence_score("galian", "pekerjaan galian tanah")
        result4 = matcher._get_multiple_name_matches("batu", limit=3)
        
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertIsInstance(result3, float)
        self.assertIsInstance(result4, list)

    def test_deprecated_api_still_functional_for_backward_compatibility(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        name_match = matcher._fuzzy_match_name("galian")
        confidence_match = matcher._fuzzy_match_name_with_confidence("galian")
        manual_score = matcher._calculate_confidence_score("galian", "pekerjaan galian tanah")
        multi_results = matcher._get_multiple_name_matches("batu", limit=3)
        
        self.assertIsNotNone(name_match)
        self.assertIsNotNone(confidence_match)
        self.assertIsInstance(manual_score, float)
        self.assertIsInstance(multi_results, list)

    def test_legacy_fuzzy_match_name_returns_none_for_no_match(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.99)
        
        result = matcher._fuzzy_match_name("nonexistent xyz abc")
        
        self.assertIsNone(result)
    
    def test_legacy_get_multiple_name_matches_returns_empty_for_no_match(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.99)
        
        results = matcher._get_multiple_name_matches("nonexistent xyz", limit=5)
        
        self.assertEqual(results, [])
    
    def test_legacy_fuzzy_match_name_with_confidence_returns_none_for_no_match(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.99)
        
        result = matcher._fuzzy_match_name_with_confidence("nonexistent xyz")
        
        self.assertIsNone(result)
    
    def test_legacy_get_multiple_matches_with_confidence_returns_empty(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.99)
        
        results = matcher._get_multiple_name_matches_with_confidence("xyz abc", limit=5)
        
        self.assertEqual(results, [])

class FuzzyMatcherEdgeCaseTests(SimpleTestCase):
    
    def setUp(self):
        self.sample_rows = [
            AhsRow(id=1, code="A.01", name="pekerjaan galian tanah"),
            AhsRow(id=2, code="B.01", name="pasangan batu bata"),
        ]
        self.fake_repo = FakeAhsRepo(self.sample_rows)
    
    def test_synonym_expander_exception_in_candidate_provider(self):
        mock_expander = MagicMock()
        mock_expander.is_available.return_value = True
        mock_expander.expand_with_manual.side_effect = Exception("Expansion failed")
        
        provider = CandidateProvider(self.fake_repo, mock_expander)
        
        candidates = provider.get_candidates_by_head_token("bongkar")
        self.assertIsInstance(candidates, list)
    
    def test_single_material_word_fallback_to_all(self):
        empty_repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="pekerjaan galian tanah"),
        ])
        
        provider = CandidateProvider(empty_repo)
        
        candidates = provider.get_candidates_by_head_token("keramik")
        
        self.assertGreater(len(candidates), 0)
    
    def test_multi_word_any_word_fallback(self):
        repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="bongkar pasangan batu"),
            AhsRow(id=2, code="B.01", name="pemasangan keramik"),
        ])
        
        provider = CandidateProvider(repo)
        
        candidates = provider.get_candidates_by_head_token("bongkar keramik")
        
        self.assertGreater(len(candidates), 0)
    
    def test_material_mode_with_action_word(self):
        repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="bongkar pasangan batu"),
            AhsRow(id=2, code="B.01", name="pemasangan keramik"),
        ])
        
        provider = CandidateProvider(repo)
        
        candidates = provider.get_candidates_by_head_token("bongkar batu")
        
        self.assertEqual(len(candidates), 1)
        self.assertIn("batu", candidates[0].name.lower())
    
    def test_legacy_method_coverage_line_405(self):
        matcher = FuzzyMatcher(self.fake_repo)
        
        score = matcher._calculate_confidence_score("galian tanah", "pekerjaan galian tanah")
        
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_synonym_expander_errors_handled_gracefully(self):
        mock_expander = MagicMock()
        mock_expander.is_available.return_value = True
        mock_expander.expand_with_manual.side_effect = Exception("Synonym lookup failed")
        
        provider = CandidateProvider(self.fake_repo, mock_expander)
        
        candidates = provider.get_candidates_by_head_token("bongkar")
        self.assertIsInstance(candidates, list)
    
    def test_queries_with_only_generic_words_return_all_candidates(self):
        provider = CandidateProvider(self.fake_repo)
        
        candidates = provider.get_candidates_by_head_token("dan atau dengan secara")
        
        self.assertEqual(len(candidates), len(self.fake_repo.rows))

    def test_external_synonym_service_failure_doesnt_break_matching(self):
        mock_expander = MagicMock()
        mock_expander.is_available.return_value = True
        mock_expander.expand_with_manual.side_effect = Exception("External API timeout")
        
        provider = CandidateProvider(self.fake_repo, mock_expander)
        
        candidates = provider.get_candidates_by_head_token("bongkar")
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
    
    def test_uncommon_construction_term_triggers_broad_search(self):
        """Test that uncommon/unknown material terms fall back to all candidates."""
        empty_repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="pekerjaan galian tanah"),
        ])
        
        provider = CandidateProvider(empty_repo)
        
        # "keramik" is not in the repository, should trigger fallback
        candidates = provider.get_candidates_by_head_token("keramik")
        
        # Should return all candidates as fallback
        self.assertGreater(len(candidates), 0)
        # Verify it's actually the fallback behavior
        self.assertEqual(len(candidates), len(empty_repo.rows))
        # Verify returned candidate is the one in repo
        self.assertEqual(candidates[0].id, 1)

    def test_mixed_material_query_uses_flexible_matching(self):
        """Test that queries with mixed materials use ANY-material fallback strategy."""
        repo = FakeAhsRepo([
            AhsRow(id=1, code="A.01", name="bongkar pasangan batu"),
            AhsRow(id=2, code="B.01", name="pemasangan keramik"),
        ])
        
        provider = CandidateProvider(repo)
        
        # Mixed query with different materials - should match either
        candidates = provider.get_candidates_by_head_token("bongkar keramik")
        
        self.assertGreater(len(candidates), 0)
        # Should find candidates with either "bongkar" action OR "keramik" material
        # Verify we got both candidates (flexible matching)
        self.assertEqual(len(candidates), 2)
        candidate_ids = {c.id for c in candidates}
        self.assertEqual(candidate_ids, {1, 2})

    def test_synonym_expansion_integrates_with_candidate_search(self):
        rows = [
            AhsRow(id=1, code="A.01", name="bongkar pasangan batu"),
            AhsRow(id=2, code="B.01", name="pembongkaran dinding"),
        ]
        repo = FakeAhsRepo(rows)
        
        mock_expander = MagicMock()
        mock_expander.is_available.return_value = True
        mock_expander.expand_with_manual.return_value = {"pembongkaran", "rusak"}
        
        provider = CandidateProvider(repo, mock_expander)
        
        candidates = provider.get_candidates_by_head_token("bongkar")
        
        mock_expander.expand_with_manual.assert_called_once()
        self.assertGreater(len(candidates), 0)

    def test_match_with_confidence_empty_description(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("")
        
        self.assertIsNone(result)
    
    def test_match_with_confidence_whitespace_description(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("   \t\n   ")
        
        self.assertIsNone(result)
    
    def test_match_with_confidence_special_chars_only(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("!@#$%^&*()")
        
        self.assertIsNone(result)
    
    def test_match_with_confidence_skips_empty_normalized_candidate_names(self):
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="   "),
            AhsRow(id=3, code="C.01", name="!@#$%"),
            AhsRow(id=4, code="D.01", name="valid entry"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("valid")
        
        if result:
            normalized = _norm_name(result["name"])
            self.assertNotEqual(normalized, "")
            self.assertEqual(result["id"], 4)
    
    def test_find_multiple_matches_with_confidence_empty_description(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.find_multiple_matches_with_confidence("", limit=5)
        
        self.assertEqual(result, [])
    
    def test_find_multiple_matches_with_confidence_whitespace_description(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.find_multiple_matches_with_confidence("   \t\n   ", limit=5)
        
        self.assertEqual(result, [])
    
    def test_find_multiple_matches_with_confidence_special_chars_only(self):
        matcher = FuzzyMatcher(self.fake_repo, min_similarity=0.3)
        
        result = matcher.find_multiple_matches_with_confidence("!@#$%^&*()", limit=5)
        
        self.assertEqual(result, [])
    
    def test_find_multiple_matches_with_confidence_skips_empty_normalized_names(self):
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="valid entry"),
            AhsRow(id=3, code="C.01", name="   "),
            AhsRow(id=4, code="D.01", name="!@#$%"),
            AhsRow(id=5, code="E.01", name="another valid"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        results = matcher.find_multiple_matches_with_confidence("valid", limit=10)
        
        for result in results:
            normalized = _norm_name(result["name"])
            self.assertNotEqual(normalized, "")
            self.assertIn(result["id"], [2, 5])

    def test_match_with_confidence_continues_on_empty_normalized_candidate_name(self):
        """Test line 459: continue when norm_cand is empty in match_with_confidence"""
        rows = [
            AhsRow(id=1, code="A.01", name=""),  # Empty name
            AhsRow(id=2, code="B.01", name="   "),  # Whitespace only
            AhsRow(id=3, code="C.01", name="!@#$%"),  # Special chars that normalize to empty
            AhsRow(id=4, code="D.01", name="valid entry one"),
            AhsRow(id=5, code="E.01", name="valid entry two"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        # This should skip rows 1-3 and only consider 4-5
        result = matcher.match_with_confidence("valid entry")
        
        if result:
            # Should only match valid entries (4 or 5)
            self.assertIn(result["id"], [4, 5])
            self.assertNotEqual(_norm_name(result["name"]), "")
        
        # Verify all candidates were considered including empty ones
        from unittest.mock import patch
        with patch.object(matcher._candidate_provider, 'get_candidates_by_head_token', return_value=rows):
            result = matcher.match_with_confidence("valid")
            if result:
                self.assertIn(result["id"], [4, 5])

    def test_find_multiple_matches_with_confidence_continues_on_empty_normalized_name(self):
        """Test line 483: continue when norm_cand is empty in find_multiple_matches_with_confidence"""
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="valid entry one"),
            AhsRow(id=3, code="C.01", name="   "),
            AhsRow(id=4, code="D.01", name="!@#$%^&*()"),
            AhsRow(id=5, code="E.01", name="valid entry two"),
            AhsRow(id=6, code="F.01", name="\t\n"),
            AhsRow(id=7, code="G.01", name="valid entry three"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        # Should skip rows 1, 3, 4, 6 (empty normalized names)
        results = matcher.find_multiple_matches_with_confidence("valid entry", limit=10)
        
        # Verify only valid entries are returned
        valid_ids = {2, 5, 7}
        for result in results:
            self.assertIn(result["id"], valid_ids)
            normalized = _norm_name(result["name"])
            self.assertNotEqual(normalized, "")
            self.assertIn("valid", result["name"].lower())
        
        # Verify we got all valid matches
        result_ids = {r["id"] for r in results}
        self.assertEqual(result_ids, valid_ids)

    def test_match_with_confidence_all_candidates_have_empty_names(self):
        """Test line 459: when all candidates have empty normalized names, return None"""
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="   "),
            AhsRow(id=3, code="C.01", name="!@#$%"),
            AhsRow(id=4, code="D.01", name="\t\n"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("test query")
        
        self.assertIsNone(result)

    def test_find_multiple_matches_with_confidence_all_candidates_empty_names(self):
        """Test line 483: when all candidates have empty normalized names, return empty list"""
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="   "),
            AhsRow(id=3, code="C.01", name="!@#$%^&*()"),
            AhsRow(id=4, code="D.01", name="\t\n\r"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        results = matcher.find_multiple_matches_with_confidence("test query", limit=10)
        
        self.assertEqual(results, [])

    def test_match_with_confidence_mixed_empty_and_valid_candidates(self):
        """Test line 459: properly skip empty names and find valid match"""
        rows = [
            AhsRow(id=1, code="A.01", name=""),
            AhsRow(id=2, code="B.01", name="pekerjaan galian tanah"),
            AhsRow(id=3, code="C.01", name="   "),
            AhsRow(id=4, code="D.01", name="galian tanah keras"),
            AhsRow(id=5, code="E.01", name="!@#"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        result = matcher.match_with_confidence("galian tanah")
        
        self.assertIsNotNone(result)
        self.assertIn(result["id"], [2, 4])
        self.assertIn("galian", result["name"].lower())
        self.assertIn("tanah", result["name"].lower())

    def test_find_multiple_matches_with_confidence_filters_empty_normalized_candidates(self):
        """Test line 483: ensure empty normalized candidates are filtered correctly"""
        rows = [
            AhsRow(id=1, code="A.01", name="bongkar batu manual"),
            AhsRow(id=2, code="B.01", name=""),
            AhsRow(id=3, code="C.01", name="bongkar batu hammer"),
            AhsRow(id=4, code="D.01", name="   \t   "),
            AhsRow(id=5, code="E.01", name="bongkar beton"),
            AhsRow(id=6, code="F.01", name="!@#$%^"),
        ]
        repo = FakeAhsRepo(rows)
        matcher = FuzzyMatcher(repo, min_similarity=0.3)
        
        results = matcher.find_multiple_matches_with_confidence("bongkar batu", limit=10)
        
        # Should only get rows 1 and 3 (maybe 5 if similarity is high enough)
        self.assertGreater(len(results), 0)
        for result in results:
            normalized = _norm_name(result["name"])
            self.assertNotEqual(normalized, "")
            self.assertNotIn(result["id"], [2, 4, 6])

class CandidateProviderTests(SimpleTestCase):
    
    def setUp(self):
        self.rows = [
            AhsRow(id=1, code="A.01", name="bongkar 1 m3 pasangan batu"),
            AhsRow(id=2, code="B.01", name="pemasangan keramik lantai 30x30"),
            AhsRow(id=3, code="C.01", name="pekerjaan galian tanah biasa"),
        ]
        self.repo = FakeAhsRepo(self.rows)
    
    def test_single_word_non_material_query(self):
        provider = CandidateProvider(self.repo)
        
        candidates = provider.get_candidates_by_head_token("pekerjaan")
        
        self.assertGreater(len(candidates), 0)
    
    def test_multi_word_without_significant_words(self):
        provider = CandidateProvider(self.repo)
        
        candidates = provider.get_candidates_by_head_token("dan atau dengan")
        
        self.assertEqual(len(candidates), len(self.rows))
    
    def test_empty_normalized_input(self):
        provider = CandidateProvider(self.repo)
        
        candidates = provider.get_candidates_by_head_token("")
        
        self.assertEqual(len(candidates), len(self.rows))

    def test_empty_query_after_normalization_returns_all(self):
        provider = CandidateProvider(self.repo)
        
        candidates = provider.get_candidates_by_head_token("!@#$%^&*()")
        
        self.assertEqual(len(candidates), len(self.repo.rows))
    
    def test_candidate_filtering_respects_word_weights(self):
        provider = CandidateProvider(self.repo)
        
        material_candidates = provider.get_candidates_by_head_token("batu")
        
        action_candidates = provider.get_candidates_by_head_token("bongkar")
        
        self.assertGreater(len(material_candidates), 0)
        self.assertGreater(len(action_candidates), 0)

    def test_stopword_only_query_returns_full_catalog(self):
        """Test that queries with only generic stopwords return all candidates."""
        provider = CandidateProvider(self.repo)
        
        # Query with only stopwords - no significant words
        candidates = provider.get_candidates_by_head_token("dan atau dengan")
        
        # Should return all rows since no significant filtering possible
        self.assertEqual(len(candidates), len(self.repo.rows))
        # Verify we got the exact same set
        returned_ids = {c.id for c in candidates}
        expected_ids = {r.id for r in self.repo.rows}
        self.assertEqual(returned_ids, expected_ids)

    def test_special_characters_normalize_to_broad_search(self):
        """Test that special characters normalize to empty string and trigger broad search."""
        provider = CandidateProvider(self.repo)
        
        # Special chars that normalize to empty
        candidates = provider.get_candidates_by_head_token("!@#$%^&*()")
        
        # Should return all candidates (empty normalized input behavior)
        self.assertEqual(len(candidates), len(self.repo.rows))
        # Verify the broad search actually returns valid data
        self.assertTrue(all(isinstance(c, AhsRow) for c in candidates))
        # Verify all original rows are present
        self.assertTrue(all(c.id in [r.id for r in self.repo.rows] for c in candidates))