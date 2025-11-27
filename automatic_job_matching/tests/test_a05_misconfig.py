from django.test import TestCase

from automatic_job_matching.service.translation_service import TranslationService


class A05SecurityMisconfigurationTests(TestCase):

    def setUp(self):
        self.ts = TranslationService()

    def test_input_size_too_large(self):
        long_text = "a" * 6000
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian(long_text)

    def test_block_sql_like_payload(self):
        payload = "DROP TABLE users;"
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian(payload)

    def test_timeout_translation(self):
        self.ts.translator.translate = lambda x: __import__("time").sleep(10)
        
        result = self.ts.translate_to_indonesian("hello world")
        self.assertIn("timeout", result.lower())

    def test_malformed_input_detection(self):
        malformed_input = "eyJ1c2VyIj6ICJhZG1pbiJ9" * 100  # base64-like string
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian(malformed_input)

    def test_safe_input_passes(self):
        safe_text = "This is a safe and normal text."
        result = self.ts.translate_to_indonesian(safe_text)
        self.assertIsNotNone(result)

