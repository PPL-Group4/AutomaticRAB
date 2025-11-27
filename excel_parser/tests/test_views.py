from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from excel_parser import views


class ViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    # ==== detect_headers ====
    @patch("excel_parser.views.load_workbook")
    @patch("excel_parser.views.validate_excel_file")
    @patch("excel_parser.views.find_header_row", return_value=0)
    @patch("excel_parser.views.map_headers", return_value=({"no": 0}, [], {"no": "No"}))
    def test_detect_headers_success(self, mock_map, mock_find, mock_validate, mock_load):
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        mock_ws.iter_rows.return_value = [[1, 2, 3]]
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        file = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/detect_headers", {"file": file})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("mapping", resp.data)
        self.assertEqual(resp.data["mapping"], {"no": 0})

    def test_detect_headers_no_file_returns_400(self):
        resp = self.client.post("/excel_parser/detect_headers")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file is required", resp.data["detail"])

    @patch("excel_parser.views.validate_excel_file", side_effect=ValidationError("Bad Excel"))
    def test_detect_headers_invalid_excel_returns_400(self, mock_validate):
        file = SimpleUploadedFile("file.xlsx", b"bad", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/detect_headers", {"file": file})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Bad Excel", resp.data["detail"])

    @patch("excel_parser.views.load_workbook", side_effect=Exception("Workbook failed"))
    @patch("excel_parser.views.validate_excel_file")
    def test_detect_headers_unexpected_error_returns_500(self, mock_validate, mock_load):
        file = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/detect_headers", {"file": file})
        self.assertEqual(resp.status_code, 500)
        self.assertIn("Workbook failed", resp.data["detail"])

    # ==== preview_rows ====
    def test_preview_rows_wrong_method(self):
        resp = self.client.get("/excel_parser/preview_rows")
        self.assertEqual(resp.status_code, 405)

    @patch("excel_parser.views.preview_file", return_value=[{"row_key": "r1", "volume": 1}])
    @patch("excel_parser.views.validate_excel_file")
    def test_preview_rows_legacy_path(self, mock_validate, mock_preview):
        file = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/preview_rows", {"file": file})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("rows", resp.json())
        self.assertEqual(resp.json()["rows"][0]["volume"], 1)

    @patch("excel_parser.views.preview_file", return_value=[{"row_key": "r1", "volume": 1}])
    @patch("excel_parser.views.validate_excel_file")
    def test_preview_rows_extended_excel_apendo_pdf(self, mock_validate, mock_preview):
        standard = SimpleUploadedFile("std.xlsx", b"ok", content_type="application/vnd.ms-excel")
        apendo = SimpleUploadedFile("apn.xlsx", b"ok", content_type="application/vnd.ms-excel")
        pdf = SimpleUploadedFile("file.pdf", b"ok", content_type="application/pdf")

        resp = self.client.post(
            "/excel_parser/preview_rows",
            {"excel_standard": standard, "excel_apendo": apendo, "pdf_file": pdf},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("excel_standard", data)
        self.assertIn("excel_apendo", data)
        self.assertIn("pdf_file", data)

    def test_preview_rows_no_file_returns_400(self):
        resp = self.client.post("/excel_parser/preview_rows")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No file uploaded", resp.json()["detail"])

    @patch("excel_parser.views.validate_excel_file", side_effect=ValidationError("Bad file"))
    def test_preview_rows_invalid_excel_returns_400(self, mock_validate):
        bad = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/preview_rows", {"file": bad})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Bad file", resp.json()["error"])

    @patch("excel_parser.views.validate_excel_file", side_effect=Exception("Crashed"))
    def test_preview_rows_unexpected_error_returns_500(self, mock_validate):
        bad = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/preview_rows", {"file": bad})
        self.assertEqual(resp.status_code, 500)
        self.assertIn("Crashed", resp.json()["error"])

    # ==== upload_view ====
    @patch("excel_parser.views.validate_excel_file")
    def test_upload_view_excel_standard_success(self, mock_validate):
        file = SimpleUploadedFile("std.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/upload/", {"excel_standard": file})
        self.assertTemplateUsed(resp, "excel_upload.html")
        self.assertIn("success", resp.context)

    @patch("excel_parser.views.validate_excel_file")
    def test_upload_view_excel_apendo_success(self, mock_validate):
        file = SimpleUploadedFile("apendo.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/upload/", {"excel_apendo": file})
        self.assertIn("success", resp.context)

    @patch("excel_parser.views.validate_pdf_file")
    def test_upload_view_pdf_success(self, mock_validate):
        pdf = SimpleUploadedFile("f.pdf", b"ok", content_type="application/pdf")
        resp = self.client.post("/excel_parser/upload/", {"pdf_file": pdf})
        self.assertIn("success", resp.context)

    def test_upload_view_no_file_returns_400(self):
        resp = self.client.post("/excel_parser/upload/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.context)

    @patch("excel_parser.views.validate_excel_file", side_effect=ValidationError("Bad Excel"))
    def test_upload_view_validation_error_returns_400(self, mock_validate):
        file = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/upload/", {"excel_standard": file})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.context)

    @patch("excel_parser.views.validate_excel_file", side_effect=Exception("Boom"))
    def test_upload_view_unexpected_error_returns_500(self, mock_validate):
        file = SimpleUploadedFile("file.xlsx", b"ok", content_type="application/vnd.ms-excel")
        resp = self.client.post("/excel_parser/upload/", {"excel_standard": file})
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.context)

    def test_upload_view_get_renders_template(self):
        resp = self.client.get("/excel_parser/upload/")
        self.assertTemplateUsed(resp, "excel_upload.html")

    # ==== rab_converted ====
    def test_rab_converted_renders_template(self):
        resp = self.client.get("/excel_parser/rab_converted/")
        self.assertTemplateUsed(resp, "rab_converted.html")

    # ==== _apply_preview_overrides ====
    def test_apply_preview_overrides_modifies_rows_correctly(self):
        rows = [{"row_key": "r1", "volume": 1, "price": 1000}]
        overrides = {"r1": {"volume": 2, "price": 2000, "total_price": 4000}}
        views._apply_preview_overrides(rows, overrides)
        self.assertEqual(rows[0]["volume"], 2)
        self.assertEqual(rows[0]["price"], 2000)
        self.assertEqual(rows[0]["total_price"], 4000)

    def test_apply_preview_overrides_with_no_key_or_no_override(self):
        rows = [{"row_key": "r2", "volume": 1}]
        views._apply_preview_overrides(rows, {})  # should not crash
        views._apply_preview_overrides([], {"r1": {"volume": 2}})
        views._apply_preview_overrides([{"row_key": None}], {"r1": {"volume": 2}})
