from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from excel_parser.validators import validate_excel_file   

class FileValidatorTests(TestCase):
    def test_accepts_xlsx_file(self):
        file = SimpleUploadedFile(
            "dummy.xlsx",
            b"dummy",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        try:
            validate_excel_file(file)
        except ValidationError:
            self.fail("Valid .xlsx file ditolak")

    def test_accepts_xls_file(self):
        file = SimpleUploadedFile(
            "dummy.xls",
            b"dummy",
            content_type="application/vnd.ms-excel",
        )
        try:
            validate_excel_file(file)
        except ValidationError:
            self.fail("Valid .xls file ditolak")

    def test_rejects_pdf_file(self):
        file = SimpleUploadedFile("dummy.pdf", b"%PDF", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_txt_file(self):
        file = SimpleUploadedFile("dummy.txt", b"Hello", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_wrong_mimetype_for_excel(self):
        file = SimpleUploadedFile("dummy.xlsx", b"fake excel", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_empty_file_with_valid_mimetype(self):
        file = SimpleUploadedFile(
            "empty.xlsx",
            b"",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        try:
            validate_excel_file(file)
        except ValidationError:
            self.fail("File kosong dengan tipe valid harus diterima")
