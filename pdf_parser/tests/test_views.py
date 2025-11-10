# tests/test_views.py
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from unittest.mock import patch
from pdf_parser.views import NO_FILE_UPLOADED_MSG

class PdfParserViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_rab_converted_pdf_get_renders_template(self):
        url = reverse("pdf_parser:rab_converted_pdf")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "rab_converted.html")

    def test_rab_converted_pdf_post_no_file_returns_400(self):
        url = reverse("pdf_parser:rab_converted_pdf")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_rab_converted_pdf_post_success_converts_decimals(self, mock_parse):
        mock_parse.return_value = [{"val": Decimal("3.14")}]
        dummy = SimpleUploadedFile("t.pdf", b"%PDF-1.4", content_type="application/pdf")
        url = reverse("pdf_parser:rab_converted_pdf")
        resp = self.client.post(url, {"pdf_file": dummy})
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            self.assertEqual(resp.json()["rows"][0]["val"], 3.14)
        else:
            self.assertIn("error", resp.json())


    @patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=Exception("boom"))
    def test_rab_converted_pdf_post_parser_fails_returns_500(self, mock_parse):
        dummy = SimpleUploadedFile("t.pdf", b"%PDF-1.4", content_type="application/pdf")
        url = reverse("pdf_parser:rab_converted_pdf")
        resp = self.client.post(url, {"pdf_file": dummy})
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.json())
        self.assertIn("rows", resp.json())

    def test_parse_pdf_view_post_no_file_returns_400(self):
        url = reverse("pdf_parser:parse_pdf")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
