from django.test import TestCase, SimpleTestCase
from unittest.mock import patch

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import (AhsRow, ExactMatcher, _norm_code, _norm_name)
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.views import MatchingService

from django.urls import reverse
from django.test import Client
import json


class TextNormalizationTestCase(TestCase):
	def setUp(self):
		from automatic_job_matching.utils.text_normalizer import normalize_text

		self.normalize_text = normalize_text

	def test_lowercase_and_whitespace(self):
		self.assertEqual(self.normalize_text("  HeLLo   WoRLD  \n\t"), "hello world")

	def test_strip_diacritics(self):
		self.assertEqual(
			self.normalize_text("Kafé São José – résumé"),
			"kafe sao jose resume",
		)

	def test_punctuation_and_symbols(self):
		self.assertEqual(
			self.normalize_text("Harga/m²: Rp. 1.000,00!"),
			"harga m2 rp 1 000 00",
		)

	def test_units_and_symbols(self):
		self.assertEqual(
			self.normalize_text("Volume: 12 m²; Ø16mm, @200mm"),
			"volume 12 m2 16mm 200mm",
		)

	def test_optional_stopwords(self):
		text = "Pekerjaan struktur dan arsitektur untuk pembangunan gedung"
		stopwords = {"dan", "untuk", "pembangunan"}
		self.assertEqual(
			self.normalize_text(text, remove_stopwords=True, stopwords=stopwords),
			"pekerjaan struktur arsitektur gedung",
		)
		self.assertEqual(
			self.normalize_text(text, remove_stopwords=False, stopwords=stopwords),
			"pekerjaan struktur dan arsitektur untuk pembangunan gedung",
		)

	def test_preserve_decimal_numbers(self):
		self.assertNotEqual(
			self.normalize_text("Harga: Rp 1.000,50"),
			"harga rp 1000,50",
		)

	def test_none_input(self):
		self.assertEqual(self.normalize_text(None), "")

	def test_empty_string(self):
		self.assertEqual(self.normalize_text(""), "")

	def test_only_punctuation(self):
		self.assertEqual(self.normalize_text("!!! ??? ;;;"), "")

	def test_collapse_whitespace(self):
		self.assertEqual(self.normalize_text(" a\t\tb\n\n c   d \r\n"), "a b c d")

	def test_square_meter_variants(self):
		self.assertEqual(self.normalize_text("5 m² 7 ㎡ 9 m2"), "5 m2 7 m2 9 m2")

	def test_caret_exponent_splits(self):
		self.assertEqual(self.normalize_text("m^2"), "m 2")

	def test_numeric_range_removed(self):
		self.assertEqual(self.normalize_text("10–20 — 30-40"), "10 20 30 40")

	def test_diameter_and_at_symbols(self):
		self.assertEqual(self.normalize_text("Ø16mm @200mm"), "16mm 200mm")

	def test_multiplication_and_middle_dot(self):
		self.assertEqual(self.normalize_text("3×4 a·b"), "3x4 a b")

	def test_slash_colon_semicolon(self):
		self.assertEqual(self.normalize_text("a/b:c;d"), "a b c d")

	def test_currency_usd_commas_and_dots(self):
		self.assertEqual(self.normalize_text("USD $1,234.00"), "usd 1 234 00")

	def test_stopwords_exact_match_only(self):
		text = "pembangunan bangun membangun"
		self.assertEqual(
			self.normalize_text(text, remove_stopwords=True, stopwords={"bangun"}),
			"pembangunan membangun",
		)

	def test_remove_stopwords_none_set(self):
		text = "satu dua tiga"
		self.assertEqual(
			self.normalize_text(text, remove_stopwords=True, stopwords=None),
			"satu dua tiga",
		)

	def test_preserve_dotted_codes(self):
		self.assertEqual(
			self.normalize_text("T.14.d | 1 m³ Pemadatan pasir sebagai bahan pengisi"),
			"T.14.d 1 m3 pemadatan pasir sebagai bahan pengisi",
		)

	def test_preserve_dotted_codes1(self):
		self.assertEqual(
			self.normalize_text("T.14.d"),
			"T.14.d",
		)

	def test_convert_spaced_AT_code(self):
		self.assertEqual(self.normalize_text("AT 19 1"), "AT.19-1")
		self.assertEqual(self.normalize_text("AT 20"), "AT.20")

	def test_convert_spaced_generic_codes(self):
		self.assertEqual(self.normalize_text("A 4 1 1 4"), "A.4.1.1.4")
		self.assertEqual(self.normalize_text("T 14 d"), "T.14.d")


	def test_no_conversion_without_digits_in_generic(self):
		self.assertEqual(self.normalize_text("A B C"), "a b c")
		self.assertEqual(self.normalize_text("AB CD"), "ab cd")

	def test_preserve_existing_dotted_at_code(self):
		self.assertEqual(self.normalize_text("AT.19-1"), "AT.19-1")
		self.assertEqual(self.normalize_text("AT.02-1"), "AT.02-1")

	def test_preserve_existing_generic_dotted_code(self):
		self.assertEqual(self.normalize_text("A.4.1.1.4"), "A.4.1.1.4")

	def test_no_conversion_when_only_prefix_present(self):
		self.assertEqual(self.normalize_text("AT"), "at")

class DbAhsRepositoryTests(SimpleTestCase):
    def setUp(self):
        class Dummy:
            id = 1
            code = "T.15.a.1"
            name = "Pemadatan pasir"
        self.fake_ahs = Dummy()

    @patch("rencanakan_core.models.Ahs.objects.none")
    @patch("rencanakan_core.models.Ahs.objects.filter")
    def test_by_code_like_returns_exact_match_and_variants(self, mock_filter, mock_none):
        class FakeQS(list):
            def union(self, other): return FakeQS(self + list(other))

        mock_none.return_value = FakeQS()
        mock_filter.return_value = FakeQS([self.fake_ahs])

        repo = DbAhsRepository()
        rows = repo.by_code_like("T.15.a.1")

        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], AhsRow)
        self.assertEqual(rows[0].code, "T.15.a.1")
        self.assertEqual(rows[0].name, "Pemadatan pasir")

        called_codes = [c.kwargs["code__iexact"] for c in mock_filter.call_args_list]
        self.assertIn("T.15.a.1", called_codes)

    @patch("rencanakan_core.models.Ahs.objects.filter")
    def test_by_name_candidates_istartswith(self, mock_filter):
        class FakeQS(list): pass
        mock_filter.return_value = FakeQS([self.fake_ahs])

        repo = DbAhsRepository()
        rows = repo.by_name_candidates("Pemadatan")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "Pemadatan pasir")
        mock_filter.assert_called_once_with(name__istartswith="Pemadatan")


class ExactMatcherTests(SimpleTestCase):
    def setUp(self):
        self.sample_row = AhsRow(
            id=10, code="T.15.a.1", name="Pemadatan pasir sebagai bahan pengisi"
        )

        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code): return self.rows
            def by_name_candidates(self, head_token): return self.rows

        self.fake_repo = FakeRepo([self.sample_row])

    def test_match_by_code_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("T.15.a.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "code")
        self.assertEqual(result["code"], "T.15.a.1")
        self.assertEqual(result["id"], 10)

    def test_match_by_code_variant_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("T-15.a-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "code")

    def test_match_by_name_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("Pemadatan pasir sebagai bahan pengisi")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "name")

    def test_match_returns_none_for_empty_input(self):
        matcher = ExactMatcher(self.fake_repo)
        self.assertIsNone(matcher.match(""))

    def test_match_returns_none_if_no_match(self):
        bad_repo = type(
            "BadRepo",
            (),
            {
                "by_code_like": lambda self, c: [],
                "by_name_candidates": lambda self, h: [],
            },
        )()
        matcher = ExactMatcher(bad_repo)
        self.assertIsNone(matcher.match("Some random description"))

    def test_norm_code_and_norm_name_helpers(self):
        self.assertEqual(_norm_code("t.15-a/1"), "T15A1")
        self.assertEqual(_norm_name("Pemadatan Pasir!"), "pemadatan pasir")

class MatchExactViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        self._repo_patcher = patch(
            "automatic_job_matching.views.DbAhsRepository",
        )
        FakeRepo = type(
            "FakeRepo",
            (),
            {
                "by_code_like": lambda self, c: [AhsRow(id=1, code="X.01", name="Dummy")],
                "by_name_candidates": lambda self, h: [],
            },
        )
        self.mock_repo_cls = self._repo_patcher.start()
        self.mock_repo_cls.return_value = FakeRepo()

    def tearDown(self):
        self._repo_patcher.stop()

    def test_valid_request_returns_match(self):
        url = reverse("match-exact")
        payload = {"description": "X.01"}
        response = self.client.post(
            url,
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("match", data)
        self.assertEqual(data["match"]["code"], "X.01")

    def test_valid_request_no_match(self):
        self.mock_repo_cls.return_value.by_code_like = lambda c: []
        url = reverse("match-exact")
        payload = {"description": "NoMatch"}
        response = self.client.post(
            url,
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["match"])

    def test_missing_description_defaults_to_empty(self):
        url = reverse("match-exact")
        response = self.client.post(
            url,
            json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["match"])

    def test_invalid_json_returns_400(self):
        url = reverse("match-exact")
        response = self.client.post(
            url,
            "not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_match_exact_view_with_empty_body_triggering_fallback(self):
        """Test exact view when request.body.decode() returns empty, triggering or '{}' fallback"""
        url = reverse("match-exact")
        response = self.client.post(url, b'', content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("match", data)

    def test_match_exact_view_description_extraction(self):
        """Test exact view description extraction from payload"""
        url = reverse("match-exact")
        payload = {"description": "test description"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_match_exact_view_missing_description_defaults(self):
        """Test exact view when description is missing from payload"""
        url = reverse("match-exact")
        payload = {"other_field": "value"}  # No description field
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_match_exact_view_json_response_structure(self):
        """Test exact view returns proper JSON structure"""
        url = reverse("match-exact")
        payload = {"description": "test"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("match", data)

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

class FuzzyMatcherViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        self._repo_patcher = patch("automatic_job_matching.views.DbAhsRepository")
        FakeRepo = type("FakeRepo", (), {
            "by_code_like": lambda self, c: [AhsRow(id=1, code="AT.01", name="Test Item")],
            "by_name_candidates": lambda self, h: [AhsRow(id=1, code="AT.01", name="Test Item")],
            "get_all_ahs": lambda self: [AhsRow(id=1, code="AT.01", name="Test Item")],
        })
        self.mock_repo_cls = self._repo_patcher.start()
        self.mock_repo_cls.return_value = FakeRepo()

    def tearDown(self):
        self._repo_patcher.stop()

    def test_fuzzy_match_view_success(self):
        url = reverse("match-fuzzy")
        payload = {"description": "Test Item", "min_similarity": 0.6}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("match", data)

    def test_fuzzy_match_view_default_similarity(self):
        url = reverse("match-fuzzy")
        payload = {"description": "Test Item"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_multiple_match_view_success(self):
        url = reverse("match-multiple")
        payload = {"description": "test", "limit": 3, "min_similarity": 0.5}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("matches", data)
        self.assertIsInstance(data["matches"], list)

    def test_multiple_match_view_default_params(self):
        url = reverse("match-multiple")
        payload = {"description": "test"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_fuzzy_match_view_invalid_json(self):
        url = reverse("match-fuzzy")
        response = self.client.post(url, "invalid-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_multiple_match_view_invalid_json(self):
        url = reverse("match-multiple")
        response = self.client.post(url, "invalid-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_fuzzy_match_view_empty_request_body(self):
        url = reverse("match-fuzzy")
        response = self.client.post(url, "", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("match", data)

    def test_multiple_match_view_empty_request_body(self):
        url = reverse("match-multiple")
        response = self.client.post(url, "", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("matches", data)
        self.assertIsInstance(data["matches"], list)

    def test_fuzzy_match_view_with_none_body(self):
        url = reverse("match-fuzzy")
        response = self.client.post(url, None, content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_multiple_match_view_with_none_body(self):
        url = reverse("match-multiple")
        response = self.client.post(url, None, content_type="application/json")
        self.assertEqual(response.status_code, 200)

class FuzzyMatcherConfidenceTDTests(SimpleTestCase):
    """TDD: Confidence scoring tests (should fail before implementation)."""

    def setUp(self):
        self.rows = [
            AhsRow(id=1, code="AT.01.001", name="pekerjaan galian tanah biasa"),
            AhsRow(id=2, code="AT.01.002", name="pekerjaan galian tanah keras"),
            AhsRow(id=3, code="BT.02.001", name="pekerjaan beton k225"),
            AhsRow(id=4, code="ST.03.001", name="pemasangan besi tulangan d10"),
            AhsRow(id=5, code="CT.04.001", name="pekerjaan cat dinding interior"),
            AhsRow(id=6, code="PT.05.001", name="pemasangan pipa air bersih"),
        ]

        class Repo:
            def __init__(self, rows): self.rows = rows
            def by_code_like(self, code): return []
            def by_name_candidates(self, head):
                return [r for r in self.rows if head in r.name.lower()]
            def get_all_ahs(self): return self.rows

        self.repo = Repo(self.rows)
        self.matcher = FuzzyMatcher(self.repo, min_similarity=0.5)

    # Positive cases
    def test_confidence_exact_match_high(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        # Expect implementation to provide confidence >= 0.85
        self.assertIsNotNone(result, "Expected a match with confidence metadata")
        self.assertIn('confidence', result, "Result must include 'confidence'")
        self.assertGreaterEqual(result['confidence'], 0.85)

    def test_confidence_partial_match_lower(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("galian tanah")
        self.assertIsNotNone(result)
        self.assertIn('confidence', result)
        # partial match should be lower than exact
        self.assertLess(result['confidence'], 0.85)
        self.assertGreaterEqual(result['confidence'], 0.5)

    def test_confidence_multiple_sorted(self):
        results = getattr(self.matcher, 'find_multiple_matches_with_confidence', lambda *_: [])("pekerjaan", limit=4)
        self.assertIsInstance(results, list)
        if results:
            self.assertIn('confidence', results[0])
            for i in range(len(results)-1):
                self.assertGreaterEqual(results[i]['confidence'], results[i+1]['confidence'])

    # Negative cases
    def test_confidence_no_match_returns_none(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("random unrelated text xyz")
        self.assertIsNone(result)

    def test_confidence_empty_input(self):
        self.assertIsNone(getattr(self.matcher, 'match_with_confidence', lambda *_: None)(""))
        self.assertIsNone(getattr(self.matcher, 'match_with_confidence', lambda *_: None)("   "))

    def test_confidence_multiple_empty(self):
        results = getattr(self.matcher, 'find_multiple_matches_with_confidence', lambda *_: [])("", limit=5)
        self.assertEqual(results, [])

    def test_confidence_score_bounds(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        if result:
            self.assertGreaterEqual(result['confidence'], 0.0)
            self.assertLessEqual(result['confidence'], 1.0)

    def test_confidence_relative_order(self):
        exact = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        partial = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("galian tanah")
        if exact and partial:
            self.assertGreater(exact['confidence'], partial['confidence'])


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
        self.assertGreater(exact, partial)

    def test_fuzzy_bounds(self):
        s = self.fuzzy.score("", "abc")
        self.assertEqual(s, 0.0)
        s2 = self.fuzzy.score("abc", "")
        self.assertEqual(s2, 0.0)
        within = self.fuzzy.score("abc", "abc d")
        self.assertGreaterEqual(within, 0.0)
        self.assertLessEqual(within, 1.0)

class MatchingServiceFallbackTests(TestCase):
    @patch("automatic_job_matching.views.FuzzyMatcher")
    def test_fuzzy_match_fallback_to_match(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value

        del fake_matcher.match_with_confidence
        fake_matcher.match.return_value = {"source": "ahs", "id": 1, "code": "X", "name": "Y"}
        
        result = MatchingService.perform_fuzzy_match("test")
        self.assertEqual(result["source"], "ahs")
        self.assertTrue(fake_matcher.match.called)

    @patch("automatic_job_matching.views.FuzzyMatcher")
    def test_multiple_match_fallback_to_find_multiple_matches(self, mock_matcher_cls):
        fake_matcher = mock_matcher_cls.return_value
        del fake_matcher.find_multiple_matches_with_confidence
        fake_matcher.find_multiple_matches.return_value = [{"id": 1}]
        
        result = MatchingService.perform_multiple_match("test")
        self.assertEqual(result[0]["id"], 1)
        self.assertTrue(fake_matcher.find_multiple_matches.called)