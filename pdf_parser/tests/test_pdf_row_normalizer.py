from django.test import TestCase
from pdf_parser.services.normalizer import PdfRowNormalizer


class PdfRowNormalizerTests(TestCase):

    def test_uppercase_header_keeps_letter_in_description(self):
        row = {
            "no": "",
            "uraian": "PEKERJAAN PERSIAPAN & SMKK",
            "satuan": "",
            "volume": "",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "PEKERJAAN PERSIAPAN & SMKK")

    def test_letter_with_punctuation_is_still_extracted(self):
        row = {
            "no": "",
            "uraian": "a.Peralatan P3K",
            "satuan": "set",
            "volume": "1",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "a")
        self.assertEqual(normalized["description"], "Peralatan P3K")

    def test_single_letter_word_not_split_as_roman(self):
        row = {
            "no": "",
            "uraian": "dan Reng",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "dan Reng")

    def test_numeric_fragment_without_unit_stays_in_description(self):
        row = {
            "no": "",
            "uraian": "23 Watt",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "23 Watt")

    def test_uppercase_word_not_split_as_roman(self):
        row = {
            "no": "",
            "uraian": "CNP 150.65.20.2,3",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "CNP 150.65.20.2,3")

    def test_word_number_prefix_merges_into_description(self):
        row = {
            "no": "di",
            "uraian": "uraikan dalam gambar",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "di uraikan dalam gambar")
