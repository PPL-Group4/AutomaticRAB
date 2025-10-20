from django.test import SimpleTestCase
from automatic_job_matching.service.abbreviation_service import AbbreviationService

class AbbreviationServiceTests(SimpleTestCase):
    def test_simple_replacement(self):
        self.assertEqual(
            AbbreviationService.expand("plst dinding"),
            "plester dinding",
        )

    def test_case_insensitive(self):
        self.assertEqual(
            AbbreviationService.expand("PLST DINDING"),
            "plester dinding",
        )

    def test_word_boundaries(self):
        self.assertEqual(
            AbbreviationService.expand("template_plstx"),
            "template_plstx",
        )

    def test_multiple_expansions(self):
        self.assertEqual(
            AbbreviationService.expand("plst dinding + bt belah"),
            "plester dinding + batu belah",
        )
