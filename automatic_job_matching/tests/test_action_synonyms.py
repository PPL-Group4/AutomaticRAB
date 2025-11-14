from django.test import SimpleTestCase

from automatic_job_matching.config import action_synonyms


class ActionSynonymsTests(SimpleTestCase):
    def test_get_synonyms_is_case_insensitive(self) -> None:
        result = action_synonyms.get_synonyms("Pasang")
        self.assertIn("pemasangan", result)

    def test_has_synonyms_false_for_unknown_word(self) -> None:
        self.assertFalse(action_synonyms.has_synonyms("nonexistent"))

    def test_get_all_action_words_contains_compound_materials_keys(self) -> None:
        words = action_synonyms.get_all_action_words()
        self.assertIn("pekerjaan", words)

    def test_compound_material_helpers(self) -> None:
        materials = action_synonyms.get_compound_materials()
        self.assertIn("hebel", materials)
        self.assertTrue(action_synonyms.is_compound_material("Bata Ringan"))
        self.assertFalse(action_synonyms.is_compound_material("paku"))
