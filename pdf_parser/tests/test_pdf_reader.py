import os
import pathlib
from django.test import TestCase
from pdf_parser.services.pdfreader import PdfReader, TextFragment

BASE_DIR = pathlib.Path(__file__).resolve().parent
SAMPLE_PDF = BASE_DIR / "data" / "PDFsample.pdf"


class PdfReaderTests(TestCase):
    """Tests for PdfReader service (converted from pytest)."""

    def setUp(self):
        self.reader = PdfReader()

    def test_extract_fragments_from_valid_pdf(self):
        """Reader should extract fragments with coordinates from a real PDF."""
        fragments = self.reader.extract(str(SAMPLE_PDF))
        self.assertIsInstance(fragments, list)
        self.assertGreater(len(fragments), 0)

        first = fragments[0]
        self.assertIsInstance(first, TextFragment)
        self.assertIsInstance(first.page, int)
        self.assertIsInstance(first.x, (int, float))
        self.assertIsInstance(first.y, (int, float))
        self.assertIsInstance(first.text, str)

    def test_extract_contains_expected_keywords(self):
        """Fragments should contain header-like keywords such as 'uraian' or 'volume'."""
        fragments = self.reader.extract(str(SAMPLE_PDF))
        texts = [f.text.lower().replace("\xa0", " ") for f in fragments]

        description_headers = ["uraian", "uraian pekerjaan", "deskripsi", "pekerjaan"]
        found_desc = any(any(h in t for h in description_headers) for t in texts)
        found_vol = any("volume" in t for t in texts)

        self.assertTrue(found_desc, "Expected at least one description-like header")
        self.assertTrue(found_vol, "Expected at least one 'volume' header")

    def test_extract_from_nonexistent_file_raises(self):
        """Should raise FileNotFoundError if path is invalid."""
        with self.assertRaises(FileNotFoundError):
            self.reader.extract("nonexistent.pdf")

    def test_extract_from_invalid_file_type_raises(self):
        """Should raise Exception if trying to read a non-PDF file."""
        tmp_path = os.path.join(BASE_DIR, "fake.txt")
        with open(tmp_path, "w") as f:
            f.write("this is not a pdf")

        try:
            with self.assertRaises(Exception):
                self.reader.extract(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_extract_from_corrupted_pdf_raises(self):
        """Should raise Exception if PDF is corrupted."""
        tmp_path = os.path.join(BASE_DIR, "bad.pdf")
        with open(tmp_path, "wb") as f:
            f.write(b"%PDF-1.4\nthis is junk data without EOF marker")

        try:
            with self.assertRaises(Exception):
                self.reader.extract(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
