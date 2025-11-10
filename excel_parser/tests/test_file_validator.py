from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from excel_parser.services.validators import validate_excel_file


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
            self.fail("Valid .xlsx file was rejected")

    def test_accepts_xls_file(self):
        file = SimpleUploadedFile(
            "dummy.xls",
            b"dummy",
            content_type="application/vnd.ms-excel",
        )
        try:
            validate_excel_file(file)
        except ValidationError:
            self.fail("Valid .xls file was rejected")

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
            self.fail("Empty valid Excel file was rejected")

    def test_rejects_doc_file(self):
        file = SimpleUploadedFile("dummy.doc", b"fake word", content_type="application/msword")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_docx_file(self):
        file = SimpleUploadedFile(
            "dummy.docx",
            b"fake word",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_ppt_file(self):
        file = SimpleUploadedFile("dummy.ppt", b"fake ppt", content_type="application/vnd.ms-powerpoint")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_pptx_file(self):
        file = SimpleUploadedFile(
            "dummy.pptx",
            b"fake ppt",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_csv_file(self):
        file = SimpleUploadedFile("dummy.csv", b"a,b,c\n1,2,3", content_type="text/csv")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_image_file(self):
        file = SimpleUploadedFile("image.jpg", b"\xff\xd8\xff\xe0", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_png_file(self):
        file = SimpleUploadedFile("image.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_gif_file(self):
        file = SimpleUploadedFile("image.gif", b"GIF89a", content_type="image/gif")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_zip_file(self):
        file = SimpleUploadedFile("archive.zip", b"PK\x03\x04", content_type="application/zip")
        with self.assertRaises(ValidationError):
            validate_excel_file(file)
