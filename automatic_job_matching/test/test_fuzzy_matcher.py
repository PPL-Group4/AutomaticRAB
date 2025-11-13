from django.test import TestCase
from unittest.mock import Mock, MagicMock, patch
from automatic_job_matching.service.fuzzy_matcher import (
    FuzzyMatcher,
    CandidateProvider,
    WordWeightConfig,
    SimilarityCalculator,
    MatchingProcessor,
    _filter_by_unit,
    _norm_name,
)
from automatic_job_matching.service.exact_matcher import AhsRow


class FakeAhsRepo:
    def __init__(self, rows):
        self._rows = rows

    def by_code_like(self, code):
        return []

    def by_name_candidates(self, head_token):
        head = (head_token or "").lower()
        return [r for r in self._rows if (r.name or "").lower().startswith(head)]

    def get_all_ahs(self):
        return list(self._rows)


class FilterByUnitTests(TestCase):
    """Test _filter_by_unit function."""

    def test_filter_by_unit_no_unit(self):
        """Test that no unit returns all candidates."""
        candidates = [
            AhsRow(1, "A.01", "galian tanah"),
            AhsRow(2, "A.02", "pemasangan keramik"),
        ]
        result = _filter_by_unit(candidates, None)
        self.assertEqual(len(result), 2)

    def test_filter_by_unit_with_matching_unit(self):
        """Test filtering with matching unit."""
        candidates = [
            AhsRow(1, "A.01", "Galian 1 m3 tanah"),
            AhsRow(2, "A.02", "Pemasangan 1 m2 keramik"),
        ]
        result = _filter_by_unit(candidates, "m3")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)

    def test_filter_by_unit_no_matches(self):
        """Test filtering with no matches."""
        candidates = [
            AhsRow(1, "A.01", "galian tanah"),
            AhsRow(2, "A.02", "pemasangan keramik"),
        ]
        result = _filter_by_unit(candidates, "ls")
        self.assertEqual(len(result), 0)

    def test_filter_by_unit_empty_unit_string(self):
        """Test with empty unit string."""
        candidates = [AhsRow(1, "A.01", "test")]
        result = _filter_by_unit(candidates, "")
        self.assertEqual(len(result), 1)

    def test_filter_by_unit_when_normalized_user_unit_is_none(self):
        """Test filtering when user unit normalization returns None."""
        candidates = [AhsRow(1, "A.01", "test")]

        with patch("automatic_job_matching.service.fuzzy_matcher.normalize_unit", return_value=None):
            result = _filter_by_unit(candidates, "!!invalid!!")
            self.assertEqual(len(result), 1)

    def test_filter_by_unit_when_units_not_compatible(self):
        """Test filtering when inferred and user units are incompatible."""
        candidates = [
            AhsRow(1, "A.01", "Galian 1 m3 tanah"),
            AhsRow(2, "A.02", "Pemasangan 1 m2 keramik"),
        ]
        result = _filter_by_unit(candidates, "bh")
        self.assertEqual(len(result), 0)

    def test_filter_by_unit_with_unnormalizable_unit(self):
        """Test unit filter with unit that can't be normalized."""
        candidates = [AhsRow(1, "A.01", "test")]

        with patch("automatic_job_matching.service.fuzzy_matcher.normalize_unit", return_value=None):
            result = _filter_by_unit(candidates, "invalid!!!")
            self.assertEqual(len(result), 1)


class WordWeightConfigTests(TestCase):
    """Test WordWeightConfig class."""

    def test_is_action_word(self):
        """Test action word detection."""
        self.assertTrue(WordWeightConfig._is_action_word("pemasangan"))
        self.assertTrue(WordWeightConfig._is_action_word("pembongkaran"))
        self.assertTrue(WordWeightConfig._is_action_word("galian"))
        self.assertFalse(WordWeightConfig._is_action_word("batu"))

    def test_is_technical_word(self):
        """Test technical word detection."""
        self.assertTrue(WordWeightConfig._is_technical_word("beton"))
        self.assertTrue(WordWeightConfig._is_technical_word("keramik"))
        self.assertTrue(WordWeightConfig._is_technical_word("aluminium"))
        self.assertFalse(WordWeightConfig._is_technical_word("dan"))



class SimilarityCalculatorTests(TestCase):
    """Test SimilarityCalculator class."""

    def setUp(self):
        self.calculator = SimilarityCalculator(WordWeightConfig())

    def test_calculate_sequence_similarity(self):
        """Test sequence similarity calculation."""
        score = self.calculator.calculate_sequence_similarity("batu", "batu")
        self.assertEqual(score, 1.0)

        score = self.calculator.calculate_sequence_similarity("batu", "xyz")
        self.assertLess(score, 0.5)

    def test_calculate_partial_similarity_exact_match(self):
        """Test partial similarity with exact match."""
        score = self.calculator.calculate_partial_similarity("pemasangan batu", "pemasangan batu")
        self.assertEqual(score, 1.0)

    def test_calculate_partial_similarity_partial_match(self):
        """Test partial similarity with partial match."""
        score = self.calculator.calculate_partial_similarity("pemasangan batu", "pembongkaran batu")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_calculate_partial_similarity_empty_query(self):
        """Test partial similarity with empty query."""
        score = self.calculator.calculate_partial_similarity("", "batu")
        self.assertEqual(score, 0.0)


    def test_calculate_partial_similarity_zero_total_weight(self):
        """Test calculate_partial_similarity with zero total weight."""
        score = self.calculator.calculate_partial_similarity("untuk dari", "untuk dari")
        self.assertGreater(score, 0.0)

    def test_calculate_partial_similarity_substring_matches(self):
        """Test partial similarity with substring matches."""
        score = self.calculator.calculate_partial_similarity("beton", "betonan")
        self.assertGreater(score, 0.0)

        score2 = self.calculator.calculate_partial_similarity("betonan", "beton")
        self.assertGreater(score2, 0.0)

    def test_calculate_partial_similarity_exact_word_match(self):
        """Test partial similarity when query word exactly matches candidate word (line 129)."""
        score = self.calculator.calculate_partial_similarity("beton", "beton lantai")
        self.assertGreater(score, 0.8)

    def test_calculate_partial_similarity_substring_partial_match(self):
        """Test partial similarity with substring matching (line 131)."""
        score = self.calculator.calculate_partial_similarity("beton", "betonan")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class CandidateProviderTests(TestCase):
    """Test CandidateProvider class."""

    def test_get_candidates_by_head_token_no_unit(self):
        """Test getting candidates without unit filter."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "batu belah"),
            AhsRow(2, "A.02", "batu kali"),
        ])
        provider = CandidateProvider(repo)
        candidates = provider.get_candidates_by_head_token("batu")
        self.assertEqual(len(candidates), 2)

    def test_get_candidates_by_head_token_with_unit(self):
        """Test getting candidates with unit filter."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "Galian 1 m3 tanah"),
            AhsRow(2, "A.02", "Pemasangan 1 m2 keramik"),
        ])
        provider = CandidateProvider(repo)
        candidates = provider.get_candidates_by_head_token("pemasangan", unit="m2")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].id, 2)

    def test_get_candidates_empty_input(self):
        """Test with empty input returns all."""
        repo = FakeAhsRepo([AhsRow(1, "A.01", "test")])
        provider = CandidateProvider(repo)
        candidates = provider.get_candidates_by_head_token("")
        self.assertEqual(len(candidates), 1)

    def test_try_single_word_material_query(self):
        """Test single word material query."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "beton k225"),
            AhsRow(2, "A.02", "pasir urug"),
        ])
        provider = CandidateProvider(repo)
        candidates = provider.get_candidates_by_head_token("beton")
        self.assertGreater(len(candidates), 0)

    def test_get_candidates_single_word_technical_returns_filtered(self):
        """Test single word material query returns filtered candidates (line 153)."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "beton k225"),
            AhsRow(2, "A.02", "beton k300"),
        ])
        provider = CandidateProvider(repo)

        candidates = provider.get_candidates_by_head_token("beton")
        self.assertGreater(len(candidates), 0)

    def test_get_candidates_with_synonym_expander(self):
        """Test candidate provider with synonym expander."""
        mock_expander = Mock()
        mock_expander.get_synonyms.return_value = ["pasangan", "instalasi"]

        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan batu"),
            AhsRow(2, "A.02", "pasangan keramik"),
        ])
        provider = CandidateProvider(repo, mock_expander)
        candidates = provider.get_candidates_by_head_token("pemasangan")
        self.assertGreater(len(candidates), 0)

    def test_get_candidates_with_compound_materials(self):
        """Test compound material detection."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "batu belah mesin"),
        ])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=["batu belah"]):
            with patch("automatic_job_matching.service.fuzzy_matcher.is_compound_material", return_value=True):
                candidates = provider.get_candidates_by_head_token("batu")
                self.assertGreater(len(candidates), 0)

    def test_get_candidates_when_no_compounds_detected(self):
        """Test candidate retrieval when compound detection returns empty list."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test item"),
        ])

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=[]):
            provider = CandidateProvider(repo)
            candidates = provider.get_candidates_by_head_token("test")
            self.assertGreater(len(candidates), 0)

    def test_get_candidates_when_compound_not_in_input(self):
        """Test when compound material doesn't match input query."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=["batu belah"]):
            provider = CandidateProvider(repo)
            candidates = provider.get_candidates_by_head_token("keramik")
            self.assertIsInstance(candidates, list)

    def test_get_candidates_without_synonym_expander(self):
        """Test candidate retrieval when synonym expander is None."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan"),
        ])
        provider = CandidateProvider(repo, synonym_expander=None)

        candidates = provider.get_candidates_by_head_token("pemasangan")
        self.assertGreater(len(candidates), 0)

    def test_get_candidates_when_has_synonyms_returns_false(self):
        """Test when has_synonyms check returns False."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            candidates = provider.get_candidates_by_head_token("test")
            self.assertGreater(len(candidates), 0)

    def test_check_synonym_match_when_no_synonyms_exist(self):
        """Test synonym checking when word has no synonyms."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            result = provider._check_synonym_match("word", "candidate")
            self.assertFalse(result)

    def test_check_synonym_match_when_synonym_found(self):
        """Test synonym checking when synonym is found in candidate."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["pasang", "install"]):
                result = provider._check_synonym_match("pemasangan", "pasang batu")
                self.assertTrue(result)

    def test_check_synonym_match_finds_synonym_in_candidate(self):
        """Test synonym match when synonym is found (line 228)."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["install", "pasang"]):
                result = provider._check_synonym_match("pemasangan", "install batu")
                self.assertTrue(result)

    def test_check_synonym_match_when_synonym_not_found(self):
        """Test synonym checking when synonym is not in candidate."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["xyz", "abc"]):
                result = provider._check_synonym_match("pemasangan", "batu belah")
                self.assertFalse(result)

    def test_check_fuzzy_match_with_long_words(self):
        """Test fuzzy match with words >= 6 characters."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        result = provider._check_fuzzy_match("pemasangan", "pemasangan batu")
        self.assertTrue(result)

    def test_check_fuzzy_match_finds_similar_word(self):
        """Test fuzzy match with similar long words (line 286)."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        result = provider._check_fuzzy_match("pemasangan", "pemasangan batu")
        self.assertTrue(result)

    def test_check_fuzzy_match_with_short_query_word(self):
        """Test fuzzy match when query word is < 6 characters."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        result = provider._check_fuzzy_match("abc", "anything here")
        self.assertFalse(result)

    def test_check_fuzzy_match_with_short_candidate_words(self):
        """Test fuzzy match when candidate words are < 6 characters."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        result = provider._check_fuzzy_match("pemasangan", "ab cd ef")
        self.assertFalse(result)

    def test_check_compound_material_match_when_compound_in_detected(self):
        """Test compound match when word is in detected_compounds."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        detected = {"batu": "batu belah"}

        with patch("automatic_job_matching.service.fuzzy_matcher.is_compound_material", return_value=True):
            result = provider._check_compound_material_match("batu", "batu belah mesin", detected)
            self.assertTrue(result)

    def test_check_compound_material_match_when_compound_not_in_detected(self):
        """Test compound match when word is not in detected_compounds."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        detected = {"batu": "batu belah"}
        result = provider._check_compound_material_match("keramik", "batu belah mesin", detected)
        self.assertFalse(result)

    def test_try_single_word_material_query_with_no_filtered_results(self):
        """Test single technical word that doesn't match any candidates."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "xyz abc def"),
        ])
        provider = CandidateProvider(repo)

        with patch.object(provider, "_filter_candidates_any_material", return_value=[]):
            candidates = provider.get_candidates_by_head_token("nonexistent")
            self.assertIsInstance(candidates, list)

    def test_try_multi_word_query_with_no_candidates_from_filter(self):
        """Test multi-word query with no candidates after filtering."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "xyz"),
        ])
        provider = CandidateProvider(repo)

        with patch.object(provider, "_filter_candidates_all_words", return_value=[]):
            with patch.object(provider, "_try_multi_word_fallback", return_value=None):
                candidates = provider.get_candidates_by_head_token("word1 word2 word3 word4")
                self.assertIsInstance(candidates, list)

    def test_try_multi_word_fallback_with_no_material_words(self):
        """Test multi-word fallback when no material words identified."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        provider = CandidateProvider(repo)

        result = provider._try_multi_word_fallback(
            ["word1", "word2"],
            [],
            repo.get_all_ahs(),
            {}
        )
        self.assertIsNone(result)

    def test_candidate_matches_any_material_when_material_in_name(self):
        """Test material matching when material is in candidate name."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        result = provider._candidate_matches_any_material("batu belah", ["batu"], {})
        self.assertTrue(result)

    def test_candidate_matches_any_material_when_no_match(self):
        """Test material matching when material not in name and no synonyms."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            result = provider._candidate_matches_any_material("xyz abc", ["beton", "keramik"], {})
            self.assertFalse(result)

    def test_candidate_matches_any_material_via_compound(self):
        """Test material matching via compound material."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.is_compound_material", return_value=True):
            result = provider._candidate_matches_any_material(
                "batu belah",
                ["batu"],
                {"batu": "batu belah"}
            )
            self.assertTrue(result)

    def test_candidate_matches_material_via_compound_match(self):
        """Test candidate matching via compound material (line 344)."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        detected = {"batu": "batu belah"}
        result = provider._candidate_matches_any_material("batu belah mesin", ["batu"], detected)
        self.assertTrue(result)

    def test_candidate_matches_any_material_via_synonym(self):
        """Test material matching via synonym."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["batu"]):
                result = provider._candidate_matches_any_material("batu", ["pasangan"], {})
                self.assertTrue(result)

    def test_candidate_matches_material_via_synonym_list(self):
        """Test candidate matching via synonym (lines 396-397)."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["install"]):
                result = provider._candidate_matches_any_material("install batu", ["pemasangan"], {})
                self.assertTrue(result)

    def test_try_material_filter_mode_with_no_materials(self):
        """Test material filter mode when no material words present."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        provider = CandidateProvider(repo)

        result = provider._try_material_filter_mode([])
        self.assertIsNone(result)

    def test_get_synonyms_to_search_when_has_synonyms_returns_false(self):
        """Test synonym search when has_synonyms returns False."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo, synonym_expander=None)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            tokens = provider._get_synonyms_to_search("word")
            self.assertEqual(len(tokens), 1)
            self.assertIn("word", tokens)

    def test_get_synonyms_adds_config_synonyms(self):
        """Test adding config synonyms to search tokens (lines 428-430)."""
        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo, synonym_expander=None)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["install", "pasang"]):
                tokens = provider._get_synonyms_to_search("pemasangan")
                self.assertGreater(len(tokens), 1)
                self.assertIn("pemasangan", tokens)

    def test_get_synonyms_to_search_with_embedding_synonyms_empty(self):
        """Test synonym search when embedding synonyms returns empty list."""
        mock_expander = Mock()
        mock_expander.get_synonyms.return_value = []

        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo, mock_expander)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            tokens = provider._get_synonyms_to_search("word")
            self.assertEqual(len(tokens), 1)

    def test_get_synonyms_adds_embedding_synonyms(self):
        """Test adding embedding synonyms to search tokens (lines 454-455)."""
        mock_expander = Mock()
        mock_expander.get_synonyms.return_value = ["instalasi", "setup"]

        repo = FakeAhsRepo([])
        provider = CandidateProvider(repo, mock_expander)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            tokens = provider._get_synonyms_to_search("pemasangan")
            self.assertGreater(len(tokens), 1)

    def test_detect_compound_materials_in_input_when_compound_not_in_input(self):
        """Test compound detection when compound not found in input."""
        repo = FakeAhsRepo([])

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=["batu belah", "pasir urug"]):
            provider = CandidateProvider(repo)
            detected = provider._detect_compound_materials_in_input("keramik lantai")
            self.assertEqual(len(detected), 0)

    def test_detect_compound_materials_creates_mapping(self):
        """Test compound material detection creates component mapping (lines 490-493)."""
        repo = FakeAhsRepo([])

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=["batu belah", "pasir urug"]):
            provider = CandidateProvider(repo)
            detected = provider._detect_compound_materials_in_input("pemasangan batu belah")
            self.assertIn("batu", detected)
            self.assertIn("belah", detected)
            self.assertEqual(detected["batu"], "batu belah")

    def test_synonym_expander_exception_handling(self):
        """Test synonym expander with exception."""
        mock_expander = Mock()
        mock_expander.get_synonyms.side_effect = Exception("API error")

        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan batu"),
        ])
        provider = CandidateProvider(repo, mock_expander)
        candidates = provider.get_candidates_by_head_token("pemasangan")
        self.assertGreater(len(candidates), 0)

    def test_multi_word_query_with_generic_words_filtered(self):
        """Test multi-word query with generic words filtered."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan beton dengan besi"),
            AhsRow(2, "A.02", "beton"),
        ])
        provider = CandidateProvider(repo)

        candidates = provider.get_candidates_by_head_token("pemasangan dengan beton")
        self.assertGreater(len(candidates), 0)

    def test_compound_detection_with_empty_list(self):
        """Test compound detection with no compounds."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])

        with patch("automatic_job_matching.service.fuzzy_matcher.get_compound_materials", return_value=[]):
            provider = CandidateProvider(repo)
            candidates = provider.get_candidates_by_head_token("test")
            self.assertGreater(len(candidates), 0)


class MatchingProcessorTests(TestCase):
    """Test MatchingProcessor class."""

    def test_find_best_match_returns_highest_score(self):
        """Test that best match returns highest scoring candidate."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan batu belah"),
            AhsRow(2, "A.02", "pemasangan batu kali"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        result = processor.find_best_match("pemasangan batu")
        self.assertIsNotNone(result)
        self.assertIn("id", result)

    def test_find_best_match_below_threshold(self):
        """Test that low similarity returns None."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "xyz abc"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.9)

        result = processor.find_best_match("completely different")
        self.assertIsNone(result)

    def test_find_multiple_matches_limit(self):
        """Test that limit is respected."""
        repo = FakeAhsRepo([
            AhsRow(i, f"A.{i:02d}", f"batu {i}") for i in range(1, 11)
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.1)

        results = processor.find_multiple_matches("batu", limit=5)
        self.assertLessEqual(len(results), 5)

    def test_find_multiple_matches_sorted_by_score(self):
        """Test that results are sorted by score."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan batu belah"),
            AhsRow(2, "A.02", "batu"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.3)

        results = processor.find_multiple_matches("batu", limit=2)
        if len(results) >= 2:
            self.assertIn("batu", results[0]["name"].lower())

    def test_find_best_match_with_empty_normalized_query(self):
        """Test best match when query normalizes to empty string."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        result = processor.find_best_match("   ")
        self.assertIsNone(result)

    def test_find_best_match_with_empty_candidate_name(self):
        """Test best match when candidate name is empty."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "test"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        result = processor.find_best_match("test")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)

    def test_find_best_match_skips_empty_candidate_name(self):
        """Test best match skips candidates with empty normalized names (line 549)."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "   "),
            AhsRow(3, "A.03", "valid name"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        result = processor.find_best_match("valid")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 3)

    def test_find_best_match_updates_best_score(self):
        """Test that best match updates when higher score found (lines 573, 581-582, 589)."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "batu"),
            AhsRow(2, "A.02", "batu belah"),
            AhsRow(3, "A.03", "batu belah mesin"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.3)

        result = processor.find_best_match("batu")
        self.assertIsNotNone(result)
        self.assertIn("name", result)

    def test_find_multiple_matches_with_empty_query(self):
        """Test multiple matches when query is empty."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        results = processor.find_multiple_matches("   ", limit=5)
        self.assertEqual(len(results), 0)

    def test_find_multiple_matches_skips_empty_candidate_names(self):
        """Test multiple matches skips candidates with empty names."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "test"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.5)

        results = processor.find_multiple_matches("test", limit=5)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], 2)

    def test_find_multiple_matches_skips_empty_and_appends_valid(self):
        """Test multiple matches skips empty names and appends valid ones (lines 658, 679-680, 697-698)."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "batu belah"),
            AhsRow(3, "A.03", "batu kali"),
        ])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)
        processor = MatchingProcessor(calculator, provider, 0.3)

        results = processor.find_multiple_matches("batu", limit=5)
        self.assertGreater(len(results), 0)
        self.assertEqual(len(results), 2)

    def test_min_similarity_bounds_checking_negative(self):
        """Test min_similarity bounds with negative value."""
        repo = FakeAhsRepo([])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)

        processor = MatchingProcessor(calculator, provider, -0.5)
        self.assertEqual(processor._min_similarity, 0.0)

    def test_min_similarity_bounds_checking_above_one(self):
        """Test min_similarity bounds with value > 1.0."""
        repo = FakeAhsRepo([])
        calculator = SimilarityCalculator(WordWeightConfig())
        provider = CandidateProvider(repo)

        processor = MatchingProcessor(calculator, provider, 1.5)
        self.assertEqual(processor._min_similarity, 1.0)


class FuzzyMatcherTests(TestCase):
    """Test FuzzyMatcher class."""

    def test_match_returns_result(self):
        """Test basic match functionality."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan batu"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        result = matcher.match("pemasangan batu")
        self.assertIsNotNone(result)

    def test_match_with_unit_filter(self):
        """Test match with unit filtering."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "Galian 1 m3 tanah"),
            AhsRow(2, "A.02", "Pemasangan 1 m2 keramik"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        result = matcher.match("pemasangan keramik", unit="m2")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)

    def test_match_empty_description(self):
        """Test with empty description."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)
        result = matcher.match("")
        self.assertIsNone(result)

    def test_find_multiple_matches(self):
        """Test finding multiple matches."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "batu belah"),
            AhsRow(2, "A.02", "batu kali"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        results = matcher.find_multiple_matches("batu", limit=5)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 5)

    def test_match_with_confidence(self):
        """Test match with confidence scoring."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "pemasangan keramik"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        result = matcher.match_with_confidence("pemasangan keramik")
        self.assertIsNotNone(result)
        self.assertIn("confidence", result)

    def test_find_multiple_matches_with_confidence(self):
        """Test finding multiple matches with confidence."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "batu belah"),
            AhsRow(2, "A.02", "batu kali"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        results = matcher.find_multiple_matches_with_confidence("batu", limit=5)
        self.assertGreater(len(results), 0)
        for result in results:
            self.assertIn("confidence", result)

    def test_expand_query_for_scoring(self):
        """Test query expansion with synonyms."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["pasangan", "instalasi"]):
                expanded = matcher._expand_query_for_scoring("pemasangan")
                self.assertIn("pemasangan", expanded)
                self.assertGreater(len(expanded.split()), 1)

    def test_legacy_match_by_name(self):
        """Test legacy match_by_name method."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test item"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        result = matcher.match_by_name("test item")
        self.assertIsNotNone(result)

    def test_legacy_search(self):
        """Test legacy search method."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        results = matcher.search("test", limit=5)
        self.assertIsInstance(results, list)

    def test_matcher_with_zero_limit(self):
        """Test with zero limit."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)
        results = matcher.find_multiple_matches("test", limit=0)
        self.assertEqual(len(results), 0)

    def test_matcher_with_negative_limit(self):
        """Test with negative limit."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)
        results = matcher.find_multiple_matches("test", limit=-1)
        self.assertEqual(len(results), 0)

    def test_matcher_with_very_high_similarity(self):
        """Test with very high min_similarity."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.99)
        result = matcher.match("almost test")
        self.assertIsNone(result)


    def test_matcher_with_numeric_description(self):
        """Test with numeric descriptions."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "beton k225"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)
        result = matcher.match("beton k225")
        self.assertIsNotNone(result)

    def test_match_with_confidence_on_empty_query(self):
        """Test confidence matching with empty query."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        matcher = FuzzyMatcher(repo)

        result = matcher.match_with_confidence("   ")
        self.assertIsNone(result)

    def test_find_multiple_matches_with_confidence_on_empty_query(self):
        """Test multiple confidence matches with empty query."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", "test"),
        ])
        matcher = FuzzyMatcher(repo)

        results = matcher.find_multiple_matches_with_confidence("   ")
        self.assertEqual(len(results), 0)

    def test_match_with_confidence_skips_empty_candidate_names(self):
        """Test confidence matching skips candidates with empty names."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "test"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)

        result = matcher.match_with_confidence("test")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)

    def test_match_with_confidence_skips_empty_candidates(self):
        """Test confidence matching skips empty candidate names (line 705)."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "pemasangan"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.5)

        result = matcher.match_with_confidence("pemasangan")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)


    def test_find_multiple_confidence_skips_empty_and_appends(self):
        """Test multiple confidence matches skips empty and appends valid."""
        repo = FakeAhsRepo([
            AhsRow(1, "A.01", ""),
            AhsRow(2, "A.02", "batu belah"),
            AhsRow(3, "A.03", "batu kali"),
        ])
        matcher = FuzzyMatcher(repo, min_similarity=0.3)

        results = matcher.find_multiple_matches_with_confidence("batu", limit=5)
        self.assertGreater(len(results), 0)
        for result in results:
            self.assertIn("confidence", result)
            self.assertNotEqual(result["name"], "")

    def test_expand_query_when_word_has_no_synonyms(self):
        """Test query expansion when word has no synonyms."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=False):
            expanded = matcher._expand_query_for_scoring("unknown")
            self.assertEqual(expanded, "unknown")

    def test_expand_query_limits_synonym_count(self):
        """Test that query expansion limits number of synonyms."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["syn1", "syn2", "syn3", "syn4"]):
                expanded = matcher._expand_query_for_scoring("test")
                words = expanded.split()
                self.assertLessEqual(len(words), 3)

    def test_expand_query_adds_limited_synonyms(self):
        """Test query expansion adds synonyms with limit."""
        repo = FakeAhsRepo([])
        matcher = FuzzyMatcher(repo)

        with patch("automatic_job_matching.service.fuzzy_matcher.has_synonyms", return_value=True):
            with patch("automatic_job_matching.service.fuzzy_matcher.get_synonyms", return_value=["syn1", "syn2"]):
                expanded = matcher._expand_query_for_scoring("test word")
                words = expanded.split()
                self.assertGreater(len(words), 2)

    def test_min_similarity_bounds_checking_negative(self):
        """Test FuzzyMatcher min_similarity bounds with negative value."""
        repo = FakeAhsRepo([])

        matcher = FuzzyMatcher(repo, min_similarity=-0.5)
        self.assertEqual(matcher.min_similarity, 0.0)

    def test_min_similarity_bounds_checking_above_one(self):
        """Test FuzzyMatcher min_similarity bounds with value > 1.0."""
        repo = FakeAhsRepo([])

        matcher = FuzzyMatcher(repo, min_similarity=1.5)
        self.assertEqual(matcher.min_similarity, 1.0)


class HelperFunctionTests(TestCase):
    """Test helper functions."""

    def test_norm_name_with_valid_string(self):
        """Test _norm_name with valid string."""
        self.assertEqual(_norm_name("Test Name"), "test name")

    def test_norm_name_with_none(self):
        """Test _norm_name with None."""
        self.assertEqual(_norm_name(None), "")

    def test_norm_name_with_empty_string(self):
        """Test _norm_name with empty string."""
        self.assertEqual(_norm_name(""), "")
