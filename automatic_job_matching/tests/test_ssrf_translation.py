from django.test import TestCase

from automatic_job_matching.service.translation_service import TranslationService


class SSRFProtectionTests(TestCase):

    def setUp(self):
        self.ts = TranslationService()

    def test_block_localhost_ssrf(self):
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian("http://127.0.0.1/admin")

    def test_block_aws_metadata_ssrf(self):
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian("http://169.254.169.254/latest/meta-data")

    def test_block_internal_network(self):
        with self.assertRaises(ValueError):
            self.ts.translate_to_indonesian("http://10.0.0.3/internal")

    def test_allow_normal_text(self):
        text = self.ts.translate_to_indonesian("hello world")
        self.assertIsNotNone(text)

    def test_allow_non_url(self):
        text = self.ts.translate_to_indonesian("pemasangan beton")
        self.assertIsNotNone(text)
