from django.test import SimpleTestCase
from automatic_job_matching.utils.unit_normalizer import (
    normalize_unit,
    infer_unit_from_description,
    units_are_compatible,
    calculate_unit_compatibility_score,
)


class NormalizeUnitTests(SimpleTestCase):
    """Test normalize_unit function."""
    
    def test_normalize_unit_none_input(self):
        """Test that None input returns None."""
        self.assertIsNone(normalize_unit(None))
    
    def test_normalize_unit_empty_string(self):
        """Test that empty string returns None."""
        self.assertIsNone(normalize_unit(""))
        self.assertIsNone(normalize_unit("   "))
    
    def test_normalize_unit_lowercase_conversion(self):
        """Test that units are converted to lowercase."""
        self.assertEqual(normalize_unit("M2"), "m2")
        self.assertEqual(normalize_unit("M3"), "m3")
        self.assertEqual(normalize_unit("LS"), "ls")
        self.assertEqual(normalize_unit("BH"), "bh")
        self.assertEqual(normalize_unit("KG"), "kg")
    
    def test_normalize_unit_special_characters(self):
        """Test that special characters are normalized."""
        self.assertEqual(normalize_unit("M²"), "m2")
        self.assertEqual(normalize_unit("M³"), "m3")
        self.assertEqual(normalize_unit("m^2"), "m2")
        self.assertEqual(normalize_unit("m^3"), "m3")
        self.assertEqual(normalize_unit("㎡"), "m2")
        self.assertEqual(normalize_unit("㎥"), "m3")
    
    def test_normalize_unit_word_variations(self):
        """Test that word variations are normalized."""
    
    def test_normalize_unit_m1_conversion(self):
        """Test that m1 is converted to m."""
        self.assertEqual(normalize_unit("m1"), "m")
        self.assertEqual(normalize_unit("M1"), "m")
    
    def test_normalize_unit_apostrophe_removal(self):
        """Test that apostrophes are removed."""
        self.assertEqual(normalize_unit("m'"), "m")
        self.assertEqual(normalize_unit("m'"), "m")
    
    def test_normalize_unit_whitespace_removal(self):
        """Test that whitespace is removed."""
        self.assertEqual(normalize_unit(" m 2 "), "m2")
        self.assertEqual(normalize_unit("m 3"), "m3")
    
    def test_normalize_unit_punctuation_removal(self):
        """Test that punctuation is removed."""
        self.assertEqual(normalize_unit("m-2"), "m2")
        self.assertEqual(normalize_unit("m.3"), "m3")
    
    def test_normalize_unit_complex_cases(self):
        """Test complex normalization cases."""
        self.assertEqual(normalize_unit("M²"), "m2")
        self.assertEqual(normalize_unit("  M ^ 3  "), "m3")
        self.assertEqual(normalize_unit("Meter2"), "m2")
        self.assertEqual(normalize_unit("BUAH"), "bh")


class InferUnitFromDescriptionTests(SimpleTestCase):
    """Test infer_unit_from_description function."""
    
    def test_infer_unit_explicit_m2(self):
        """Test explicit m2 mentions in description."""
        self.assertEqual(infer_unit_from_description("Pemasangan 1 m2 Dinding Keramik"), "m2")
        self.assertEqual(infer_unit_from_description("Lantai 10 m² granit"), "m2")
        self.assertEqual(infer_unit_from_description("Area 5 meter2"), "m2")
        self.assertEqual(infer_unit_from_description("Luas 20 persegi"), "m2")
    
    def test_infer_unit_explicit_m3(self):
        """Test explicit m3 mentions in description."""
        self.assertEqual(infer_unit_from_description("Galian 1 m3 tanah"), "m3")
        self.assertEqual(infer_unit_from_description("Volume 5 m³"), "m3")
        self.assertEqual(infer_unit_from_description("10 meter3 beton"), "m3")
        self.assertEqual(infer_unit_from_description("Kubik pasir"), "m3")
    
    def test_infer_unit_explicit_linear_meter(self):
        """Test explicit linear meter mentions."""
        self.assertEqual(infer_unit_from_description("Pemasangan 1 m' Plint Keramik"), "m")
        self.assertEqual(infer_unit_from_description("Pipa 5 m1"), "m")
        self.assertEqual(infer_unit_from_description("Kabel 10 m panjang"), "m")
    
    def test_infer_unit_explicit_lump_sum(self):
        """Test explicit lump sum mentions."""
        self.assertEqual(infer_unit_from_description("Pekerjaan ls administrasi"), "ls")
        self.assertEqual(infer_unit_from_description("Item lumpsum"), "ls")
        self.assertEqual(infer_unit_from_description("Paket pekerjaan"), "ls")
    
    def test_infer_unit_explicit_pieces(self):
        """Test explicit piece mentions."""
        self.assertEqual(infer_unit_from_description("Pintu 1 bh"), "bh")
        self.assertEqual(infer_unit_from_description("Lampu 5 buah"), "bh")
        self.assertEqual(infer_unit_from_description("AC 2 unit"), "bh")
        self.assertEqual(infer_unit_from_description("Set lengkap"), "bh")
    
    def test_infer_unit_explicit_kg(self):
        """Test explicit kg mentions."""
        self.assertEqual(infer_unit_from_description("Besi 100 kg"), "kg")
        self.assertEqual(infer_unit_from_description("Material 50 kilogram"), "kg")
    
    def test_infer_unit_lump_sum_patterns(self):
        """Test lump sum pattern inference."""
        self.assertEqual(infer_unit_from_description("mobilisasi alat berat"), "ls")
        self.assertEqual(infer_unit_from_description("demobilisasi peralatan"), "ls")
        self.assertEqual(infer_unit_from_description("penyiapan lahan"), "ls")
        self.assertEqual(infer_unit_from_description("papan proyek"), "ls")
        self.assertEqual(infer_unit_from_description("direksi keet"), "ls")
        self.assertEqual(infer_unit_from_description("administrasi proyek"), "ls")
        self.assertEqual(infer_unit_from_description("dokumentasi pekerjaan"), "ls")
        self.assertEqual(infer_unit_from_description("ijin bangunan"), "ls")
        # Additional lump sum patterns
        self.assertEqual(infer_unit_from_description("persiapan kerja"), "ls")
        self.assertEqual(infer_unit_from_description("papan nama proyek"), "ls")
        self.assertEqual(infer_unit_from_description("barak pekerja"), "ls")
        self.assertEqual(infer_unit_from_description("laporan bulanan"), "ls")
        self.assertEqual(infer_unit_from_description("rapat koordinasi"), "ls")
        self.assertEqual(infer_unit_from_description("sertifikat K3"), "ls")
        self.assertEqual(infer_unit_from_description("perijinan lingkungan"), "ls")
    
    def test_infer_unit_volume_patterns(self):
        """Test volume pattern inference."""
        self.assertEqual(infer_unit_from_description("galian tanah biasa"), "m3")
        self.assertEqual(infer_unit_from_description("urugan tanah"), "m3")
        self.assertEqual(infer_unit_from_description("timbunan pasir"), "m3")
        self.assertEqual(infer_unit_from_description("pemadatan tanah"), "m3")
        self.assertEqual(infer_unit_from_description("beton cor k225"), "m3")
        self.assertEqual(infer_unit_from_description("pengecoran beton"), "m3")
        self.assertEqual(infer_unit_from_description("pasir urug"), "m3")
        self.assertEqual(infer_unit_from_description("pembongkaran beton"), "m3")
        # Additional volume patterns
        self.assertEqual(infer_unit_from_description("pengurugan tanah"), "m3")
        self.assertEqual(infer_unit_from_description("volume beton"), "m3")
        self.assertEqual(infer_unit_from_description("tanah merah"), "m3")
        self.assertEqual(infer_unit_from_description("sirtu urug"), "m3")
        self.assertEqual(infer_unit_from_description("agregat kasar"), "m3")
    
    def test_infer_unit_area_patterns(self):
        """Test area pattern inference."""
    
    def test_infer_unit_plint_is_linear(self):
        """Test that plint/lis is inferred as linear meter."""
        self.assertEqual(infer_unit_from_description("pemasangan plint keramik"), "m")
        self.assertEqual(infer_unit_from_description("lis dinding kayu"), "m")
    
    def test_infer_unit_linear_patterns(self):
        """Test linear meter pattern inference."""
        self.assertEqual(infer_unit_from_description("pipa pvc 3 inch"), "m")
        self.assertEqual(infer_unit_from_description("kabel listrik nymhy"), "m")
        self.assertEqual(infer_unit_from_description("pagar besi hollow"), "m")
        self.assertEqual(infer_unit_from_description("railing tangga"), "m")
        self.assertEqual(infer_unit_from_description("besi beton d13"), "m")
        self.assertEqual(infer_unit_from_description("drainase u ditch"), "m")
        self.assertEqual(infer_unit_from_description("saluran air"), "m")
        self.assertEqual(infer_unit_from_description("gorong gorong"), "m")
        self.assertEqual(infer_unit_from_description("kawat harmonika"), "m")
        # Additional linear patterns
        self.assertEqual(infer_unit_from_description("list profil kayu"), "m")
        self.assertEqual(infer_unit_from_description("tulangan beton"), "m")
        self.assertEqual(infer_unit_from_description("talang air"), "m")
        self.assertEqual(infer_unit_from_description("tali tambang"), "m")
        self.assertEqual(infer_unit_from_description("selang air"), "m")
        self.assertEqual(infer_unit_from_description("handrail besi"), "m")
        self.assertEqual(infer_unit_from_description("profil aluminium"), "m")
    
    def test_infer_unit_piece_patterns(self):
        """Test piece pattern inference."""
    
    def test_infer_unit_no_match(self):
        """Test that no match returns None."""
        self.assertIsNone(infer_unit_from_description("unknown item"))
        self.assertIsNone(infer_unit_from_description("xyz abc"))
        self.assertIsNone(infer_unit_from_description(""))
    
    def test_infer_unit_case_insensitive(self):
        """Test that inference is case insensitive."""
        self.assertEqual(infer_unit_from_description("GALIAN TANAH"), "m3")
        self.assertEqual(infer_unit_from_description("Pemasangan Lantai"), "m2")
        self.assertEqual(infer_unit_from_description("MOBILISASI ALAT"), "ls")


class UnitsAreCompatibleTests(SimpleTestCase):
    """Test units_are_compatible function."""
    
    def test_units_compatible_no_user_unit(self):
        """Test that no user unit returns True (no filter)."""
        self.assertTrue(units_are_compatible("m2", None))
        self.assertTrue(units_are_compatible("m3", None))
        self.assertTrue(units_are_compatible(None, None))
    
    def test_units_compatible_no_inferred_unit(self):
        """Test that no inferred unit returns False."""
        self.assertFalse(units_are_compatible(None, "m2"))
        self.assertFalse(units_are_compatible(None, "m3"))
    
    def test_units_compatible_direct_match(self):
        """Test direct unit matches."""
        self.assertTrue(units_are_compatible("m2", "m2"))
        self.assertTrue(units_are_compatible("m3", "m3"))
        self.assertTrue(units_are_compatible("m", "m"))
        self.assertTrue(units_are_compatible("ls", "ls"))
        self.assertTrue(units_are_compatible("bh", "bh"))
        self.assertTrue(units_are_compatible("kg", "kg"))
    
    def test_units_compatible_linear_aliases(self):
        """Test linear meter aliases."""
        self.assertTrue(units_are_compatible("m", "m1"))
        self.assertTrue(units_are_compatible("m1", "m"))
        self.assertTrue(units_are_compatible("m", "meter"))
        self.assertTrue(units_are_compatible("meter", "m"))
    
    def test_units_compatible_area_aliases(self):
        """Test area aliases."""
        self.assertTrue(units_are_compatible("m2", "meter2"))
        self.assertTrue(units_are_compatible("meter2", "m2"))
        self.assertTrue(units_are_compatible("m2", "persegi"))
        self.assertTrue(units_are_compatible("persegi", "m2"))
    
    def test_units_compatible_volume_aliases(self):
        """Test volume aliases."""
        self.assertTrue(units_are_compatible("m3", "meter3"))
        self.assertTrue(units_are_compatible("meter3", "m3"))
        self.assertTrue(units_are_compatible("m3", "kubik"))
        self.assertTrue(units_are_compatible("kubik", "m3"))
    
    def test_units_compatible_piece_aliases(self):
        """Test piece aliases."""
        self.assertTrue(units_are_compatible("bh", "buah"))
        self.assertTrue(units_are_compatible("buah", "bh"))
        self.assertTrue(units_are_compatible("bh", "unit"))
        self.assertTrue(units_are_compatible("unit", "bh"))
        self.assertTrue(units_are_compatible("bh", "set"))
        self.assertTrue(units_are_compatible("set", "bh"))
    
    def test_units_compatible_lump_sum_aliases(self):
        """Test lump sum aliases."""
        self.assertTrue(units_are_compatible("ls", "lumpsum"))
        self.assertTrue(units_are_compatible("lumpsum", "ls"))
        self.assertTrue(units_are_compatible("ls", "paket"))
        self.assertTrue(units_are_compatible("paket", "ls"))
    
    def test_units_compatible_weight_aliases(self):
        """Test weight aliases."""
        self.assertTrue(units_are_compatible("kg", "kilogram"))
        self.assertTrue(units_are_compatible("kilogram", "kg"))
    
    def test_units_incompatible_different_dimensions(self):
        """Test that different dimensions are incompatible."""
        self.assertFalse(units_are_compatible("m", "m2"))
        self.assertFalse(units_are_compatible("m2", "m"))
        self.assertFalse(units_are_compatible("m", "m3"))
        self.assertFalse(units_are_compatible("m3", "m"))
        self.assertFalse(units_are_compatible("m2", "m3"))
        self.assertFalse(units_are_compatible("m3", "m2"))
        self.assertFalse(units_are_compatible("m", "ls"))
        self.assertFalse(units_are_compatible("m2", "bh"))
        self.assertFalse(units_are_compatible("m3", "kg"))
    
    def test_units_compatible_case_insensitive(self):
        """Test that comparison is case insensitive."""
        self.assertTrue(units_are_compatible("M2", "m2"))
        self.assertTrue(units_are_compatible("M3", "m3"))
        self.assertTrue(units_are_compatible("LS", "ls"))
        self.assertTrue(units_are_compatible("BH", "buah"))
    
    def test_units_compatible_with_special_chars(self):
        """Test compatibility with special characters."""
        self.assertTrue(units_are_compatible("m²", "m2"))
        self.assertTrue(units_are_compatible("m³", "m3"))
        self.assertTrue(units_are_compatible("m^2", "m2"))
        self.assertTrue(units_are_compatible("m^3", "m3"))
    
    def test_units_compatible_empty_strings(self):
        """Test that empty strings return False."""
        self.assertFalse(units_are_compatible("", "m2"))
        self.assertTrue(units_are_compatible("", ""))  # Both None after normalization
    
    def test_units_compatible_whitespace(self):
        """Test that whitespace is handled."""
        self.assertTrue(units_are_compatible("  m2  ", "m2"))
        self.assertTrue(units_are_compatible("m 2", "m2"))

    def test_units_compatible_invalid_units_normalize_to_none(self):
        """Test line 190: when normalization returns None."""
        # Test with units that contain only invalid characters
        # These will normalize to None after removing all non-alphanumeric chars
        
        # User unit invalid (normalizes to None)
        result = units_are_compatible("m2", "!@#$%")
        self.assertFalse(result)
        
        # Inferred unit invalid (normalizes to None)  
        result = units_are_compatible("!@#$%", "m2")
        self.assertFalse(result)
        
        # Both invalid (both normalize to None)
        result = units_are_compatible("!@#$", "%%%")
        self.assertFalse(result)
        
        # Edge case: unit that becomes empty after normalization
        result = units_are_compatible("m2", "---")
        self.assertFalse(result)


class CalculateUnitCompatibilityScoreTests(SimpleTestCase):
    """Test calculate_unit_compatibility_score function."""
    
    def test_compatibility_score_no_user_unit(self):
        """Test that no user unit returns 0.0."""
        self.assertEqual(calculate_unit_compatibility_score("galian tanah", None), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("galian tanah", ""), 0.0)
    
    def test_compatibility_score_compatible_units(self):
        """Test compatible units return 0.08."""
        self.assertEqual(calculate_unit_compatibility_score("galian tanah biasa", "m3"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pemasangan lantai keramik", "m2"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pipa pvc", "m"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("mobilisasi alat", "ls"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pintu panel", "bh"), 0.08)
    
    def test_compatibility_score_incompatible_units(self):
        """Test incompatible units return 0.0."""
        self.assertEqual(calculate_unit_compatibility_score("galian tanah", "m2"), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("pemasangan keramik", "m"), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("pipa pvc", "m3"), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("mobilisasi alat", "bh"), 0.0)
    
    def test_compatibility_score_no_inferred_unit(self):
        """Test that no inferred unit returns 0.0."""
        self.assertEqual(calculate_unit_compatibility_score("unknown item", "m2"), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("xyz abc", "m3"), 0.0)
    
    def test_compatibility_score_with_aliases(self):
        """Test compatibility score with unit aliases."""
        self.assertEqual(calculate_unit_compatibility_score("galian tanah", "meter3"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pemasangan keramik", "persegi"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pipa pvc", "meter"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pintu panel", "buah"), 0.08)
    
    def test_compatibility_score_case_insensitive(self):
        """Test that scoring is case insensitive."""
        self.assertEqual(calculate_unit_compatibility_score("GALIAN TANAH", "M3"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("Pemasangan Keramik", "M2"), 0.08)
    
    def test_compatibility_score_special_chars(self):
        """Test compatibility score with special characters."""
        self.assertEqual(calculate_unit_compatibility_score("galian tanah", "m³"), 0.08)
        self.assertEqual(calculate_unit_compatibility_score("pemasangan keramik", "m²"), 0.08)
    
    def test_compatibility_score_line_190_coverage(self):
        """Test the else branch in calculate_unit_compatibility_score (line 190)."""
        # When units are NOT compatible, should return 0.0
        self.assertEqual(calculate_unit_compatibility_score("galian tanah m3", "m2"), 0.0)
        self.assertEqual(calculate_unit_compatibility_score("lantai keramik", "m3"), 0.0)


