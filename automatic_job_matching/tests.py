from django.test import TestCase, SimpleTestCase
from unittest.mock import patch
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import (AhsRow, ExactMatcher, _norm_code, _norm_name)

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