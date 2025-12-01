from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch


class PreviewRowsStubTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("excel_parser.views.preview_file")
    @patch("excel_parser.views.validate_excel_file")
    def test_preview_rows_legacy_path_stubbed(self, mock_validate, mock_preview):
        # --- STUB: preview_file returns fixed rows ---
        mock_preview.return_value = [
            {"row_key": "abc123", "volume": 10, "price": 5000, "description": "Item A", "is_section": False}
        ]

        file = SimpleUploadedFile("test.xlsx", b"123", content_type="application/vnd.ms-excel")

        response = self.client.post("/excel_parser/preview_rows", {"file": file})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check the stubbed return is passed through the view
        self.assertIn("rows", data)
        self.assertEqual(data["rows"][0]["volume"], 10)
        self.assertEqual(data["rows"][0]["price"], 5000)

        # Ensure preview_file was called exactly once
        mock_preview.assert_called_once()
