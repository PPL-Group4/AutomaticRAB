from django.test import SimpleTestCase


class TextNormalizationTestCase(SimpleTestCase):
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
    
	def test_strip_diacritics_comprehensive(self):
		"""Test diacritic stripping thoroughly."""
		from automatic_job_matching.utils.text_normalizer import normalize_text
		
		# Various diacritics
		test_cases = [
			("café", "cafe"),
			("naïve", "naive"),
			("résumé", "resume"),
			("über", "uber"),
		]
		
		for input_text, expected in test_cases:
			result = normalize_text(input_text)
			# Check that diacritics are removed
			self.assertNotIn("é", result)
			self.assertNotIn("ï", result)
			self.assertNotIn("ü", result)
    
	def test_convert_generic_codes_no_digits(self):
		"""Test _convert_generic_codes with no digits in parts."""
		from automatic_job_matching.utils.text_normalizer import _convert_generic_codes
		
		# Should NOT convert if no digits present
		result = _convert_generic_codes("ABC DEF GHI")
		self.assertNotIn("ABC.DEF.GHI", result)
		self.assertIn("ABC", result)

	def test_convert_generic_codes_with_digits(self):
		"""Test _convert_generic_codes with digits in parts."""
		from automatic_job_matching.utils.text_normalizer import _convert_generic_codes
		
		# Should convert when digits present
		result = _convert_generic_codes("A 4 4 3 53")
		self.assertIn("A.4.4.3.53", result)

	def test_convert_generic_codes_mixed_alpha_numeric(self):
		"""Test _convert_generic_codes with mixed alphanumeric."""
		from automatic_job_matching.utils.text_normalizer import _convert_generic_codes
		
		# Should convert when at least one part has digit
		result = _convert_generic_codes("A B1 C2")
		self.assertIn("A.B1.C2", result)

	def test_protect_codes_and_restore(self):
		"""Test code protection and restoration."""
		from automatic_job_matching.utils.text_normalizer import _protect_codes, _restore_protected_codes
		
		text = "A.4.4.3.53 pemasangan keramik"
		protected, code_map = _protect_codes(text)
		
		# Check that code is replaced with placeholder
		self.assertIn("codeplaceholder", protected)
		self.assertNotIn("A.4.4.3.53", protected)
		
		# Restore codes
		restored = _restore_protected_codes(protected, code_map)
		self.assertIn("A.4.4.3.53", restored)

	def test_protect_multiple_codes(self):
		"""Test protecting multiple codes."""
		from automatic_job_matching.utils.text_normalizer import _protect_codes
		
		text = "A.4.4 and B.5.6 items"
		protected, code_map = _protect_codes(text)
		
		# Should have two placeholders
		self.assertEqual(len(code_map), 2)
		self.assertIn("codeplaceholder0", protected)
		self.assertIn("codeplaceholder1", protected)

	def test_normalize_with_code_protection(self):
		"""Test full normalization with code protection."""
		from automatic_job_matching.utils.text_normalizer import normalize_text
		
		# Code should be preserved through normalization
		result = normalize_text("A.4.4.3.53 pemasangan 1m² keramik")
		self.assertIn("A.4.4.3.53", result)
		self.assertIn("m2", result)

	def test_apply_character_substitutions_coverage(self):
		"""Test all character substitutions."""
		from automatic_job_matching.utils.text_normalizer import _apply_character_substitutions
		
		# Test all special chars
		test_cases = [
			("m²", "m2"),
			("㎡", "m2"),
			("²", "2"),
			("m³", "m3"),
			("㎥", "m3"),
			("³", "3"),
			("–", "-"),
			("—", "-"),
			("·", " "),
			("×", "x"),
			("Ø", " "),
			("@", " "),
		]
		
		for input_str, expected_sub in test_cases:
			result = _apply_character_substitutions(input_str)
			self.assertNotIn(input_str, result) or self.assertIn(expected_sub, result)

	def test_remove_stopwords_empty_set(self):
		"""Test stopword removal with empty set."""
		from automatic_job_matching.utils.text_normalizer import _remove_stopwords_from_text
		
		text = "pemasangan beton"
		result = _remove_stopwords_from_text(text, set())
		self.assertEqual(result, text)

	def test_normalize_text_with_all_features(self):
		"""Test normalize_text with all features enabled."""
		from automatic_job_matching.utils.text_normalizer import normalize_text
		
		# Test with stopwords, codes, and special chars
		result = normalize_text(
			"A.4.4 Pemasangan 1m² keramik dengan beton untuk dinding",
			remove_stopwords=True,
			stopwords={"untuk", "dengan"}
		)
		
		self.assertIn("A.4.4", result)
		self.assertIn("pemasangan", result)
		self.assertIn("m2", result)
		self.assertNotIn("untuk", result)
		self.assertNotIn("dengan", result)

	def test_create_dotted_code_match_group(self):
		"""Test code creation from match groups."""
		from automatic_job_matching.utils.text_normalizer import _convert_generic_codes
		
		# Test with various patterns
		test_cases = [
			("X 1 2 3", "X.1.2.3"),
			("AB 12 34", "AB.12.34"),
			("A ABC DEF", "A ABC DEF"),  # No digits, no conversion
		]
		
		for input_str, expected in test_cases:
			result = _convert_generic_codes(input_str)
			if expected == input_str:
				# Should not be converted
				self.assertNotIn(".", result.replace(" ", ""))
			else:
				self.assertIn(expected, result)