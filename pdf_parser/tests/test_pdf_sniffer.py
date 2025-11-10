import tempfile
from django.core.exceptions import ValidationError
from django.test import TestCase
from pdf_parser.services.pdf_sniffer import PdfSniffer


class PdfSnifferTests(TestCase):
    """Tests for content integrity (actual PDF structure)"""

    def _temp_path(self, suffix):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.close()
        return f.name

    def test_valid_pdf_file(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Some content\n%%EOF")
        sniffer = PdfSniffer()
        self.assertIsNone(sniffer.is_valid(file_path))

    def test_invalid_minimal_pdf_header(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF")
        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_fake_pdf_with_txt_content(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "w") as f:
            f.write("Hello world")
        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_corrupted_pdf_file(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\n")
        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)
