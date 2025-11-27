from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from pdf_parser.services.validators import validate_pdf_file


class FileValidatorTests(TestCase):
    """Tests for extension and mimetype validation only"""

    def test_accepts_pdf_file(self):
        file = SimpleUploadedFile("dummy.pdf", b"%PDF-1.4\n%Fake PDF", content_type="application/pdf")
        try:
            validate_pdf_file(file)
        except ValidationError:
            self.fail("Valid .pdf file was rejected")

    def test_empty_pdf_with_valid_mimetype(self):
        file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        try:
            validate_pdf_file(file)
        except ValidationError:
            self.fail("Empty but valid PDF file was rejected")

    def test_rejects_txt_file(self):
        file = SimpleUploadedFile("dummy.txt", b"hello", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_xlsx_file(self):
        file = SimpleUploadedFile("dummy.xlsx", b"fake excel", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_xls_file(self):
        file = SimpleUploadedFile("dummy.xls", b"fake excel", content_type="application/vnd.ms-excel")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_doc_file(self):
        file = SimpleUploadedFile("dummy.doc", b"fake word", content_type="application/msword")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_docx_file(self):
        file = SimpleUploadedFile("dummy.docx", b"fake word", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_ppt_file(self):
        file = SimpleUploadedFile("dummy.ppt", b"fake ppt", content_type="application/vnd.ms-powerpoint")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_pptx_file(self):
        file = SimpleUploadedFile("dummy.pptx", b"fake ppt", content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_csv_file(self):
        file = SimpleUploadedFile("dummy.csv", b"a,b,c\n1,2,3", content_type="text/csv")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_jpg_file(self):
        file = SimpleUploadedFile("image.jpg", b"\xff\xd8\xff\xe0", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_jpeg_file(self):
        file = SimpleUploadedFile("image.jpeg", b"\xff\xd8\xff\xe0", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_png_file(self):
        file = SimpleUploadedFile("image.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_gif_file(self):
        file = SimpleUploadedFile("image.gif", b"GIF89a", content_type="image/gif")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_zip_file(self):
        file = SimpleUploadedFile("archive.zip", b"PK\x03\x04", content_type="application/zip")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_wrong_extension_with_pdf_mimetype(self):
        file = SimpleUploadedFile("notpdf.txt", b"%PDF-1.4\nstuff", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_wrong_mimetype_with_pdf_extension(self):
        file = SimpleUploadedFile("tricky.pdf", b"%PDF-1.4\nstuff", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)
