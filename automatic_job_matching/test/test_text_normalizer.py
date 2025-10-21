from django.test import TestCase

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

	# def test_convert_spaced_generic_codes(self):
	# 	self.assertEqual(self.normalize_text("A 4 1 1 4"), "A.4.1.1.4")
	# 	self.assertEqual(self.normalize_text("T 14 d"), "T.14.d")
		
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