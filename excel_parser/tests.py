from io import BytesIO
from decimal import Decimal
import tempfile
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from excel_parser.header_mapper import map_headers, find_header_row
from excel_parser.validators import validate_excel_file
from excel_parser.services import ExcelSniffer, create_rab_parser
from excel_parser.reader import ExcelImporter, UnsupportedFileError
from excel_parser.models import Project, RabEntry
from datetime import date

from openpyxl import Workbook

try:
    import xlrd
    from xlwt import Workbook as XlsWorkbook
except ImportError:
    xlrd = None
    XlsWorkbook = None


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

class ExcelSnifferTests(TestCase):
    def _temp_path(self, suffix):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.close()
        return f.name

    def test_valid_xlsx_file(self):
        file_path = self._temp_path(".xlsx")
        wb = Workbook()
        wb.save(file_path)

        sniffer = ExcelSniffer()
        self.assertIsNone(sniffer.is_valid(file_path))

    def test_valid_empty_xlsx_file(self):
        file_path = self._temp_path(".xlsx")
        wb = Workbook()
        wb.save(file_path)

        sniffer = ExcelSniffer()
        self.assertIsNone(sniffer.is_valid(file_path))

    def test_invalid_xlsx_file(self):
        file_path = self._temp_path(".xlsx")
        with open(file_path, "wb") as f:
            f.write(b"not really excel")

        sniffer = ExcelSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_fake_xlsx_with_wrong_content(self):
        file_path = self._temp_path(".xlsx")
        with open(file_path, "w") as f:
            f.write("Hello world")

        sniffer = ExcelSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_valid_xls_file(self):
        if not XlsWorkbook:
            self.skipTest("xlrd/xlwt not installed")

        file_path = self._temp_path(".xls")
        wb = XlsWorkbook()
        sheet = wb.add_sheet("Sheet1")
        sheet.write(0, 0, "Hello XLS")
        wb.save(file_path)

        sniffer = ExcelSniffer()
        self.assertIsNone(sniffer.is_valid(file_path))

    def test_invalid_xls_file(self):
        if not xlrd:
            self.skipTest("xlrd not installed")

        file_path = self._temp_path(".xls")
        with open(file_path, "wb") as f:
            f.write(b"not really an xls")

        sniffer = ExcelSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)


class ExcelReaderTests(TestCase):
    def _xlsx_file(self):
        bio = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan"])
        ws.append([1, "Pondasi", 10.5, "m3"])
        ws.append([2, "Beton Kolom", "1.000,5", "m3"])  # Indonesian number style
        wb.save(bio)
        return SimpleUploadedFile(
            "rab.xlsx",
            bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _xls_file(self):
        if not XlsWorkbook:
            self.skipTest("xlwt not installed")
        bio = BytesIO()
        wb = XlsWorkbook()
        ws = wb.add_sheet("Sheet1")
        rows = [
            ["No", "Uraian Pekerjaan", "Volume", "Satuan"],
            [1, "Pondasi", 3.25, "m3"],
            ["1.2", "Urugan", "2.500,00", "m3"],
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                ws.write(r, c, val)
        wb.save(bio)
        return SimpleUploadedFile(
            "rab.xls",
            bio.getvalue(),
            content_type="application/vnd.ms-excel",
        )

    def test_read_xlsx_into_db(self):
        f = self._xlsx_file()
        count = ExcelImporter().import_file(f)
        self.assertEqual(count, 2)
        self.assertEqual(RabEntry.objects.count(), 2)

        first = RabEntry.objects.order_by("row_index").first()
        self.assertEqual(first.description, "Pondasi")
        self.assertEqual(first.unit, "m3")
        self.assertEqual(first.volume, Decimal("10.5"))

        # Indonesian-style number parsed
        second = RabEntry.objects.order_by("row_index")[1]
        self.assertEqual(second.volume, Decimal("1000.5"))

    def test_read_xls_into_db(self):
        f = self._xls_file()
        # test skipped above if xlwt not installed
        count = ExcelImporter().import_file(f)
        self.assertEqual(count, 2)
        self.assertEqual(RabEntry.objects.count(), 2)

    def test_header_variants(self):
        # Accept e.g. "Uraian", "Deskripsi", "Qty" for robustness
        bio = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian", "Qty", "Satuan"])
        ws.append(["A", "Pekerjaan A", "12", "m2"])
        wb.save(bio)
        f = SimpleUploadedFile(
            "alt.xlsx",
            bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        count = ExcelImporter().import_file(f)
        self.assertEqual(count, 1)
        item = RabEntry.objects.get()
        self.assertEqual(item.item_number, "A")
        self.assertEqual(item.unit, "m2")
        self.assertEqual(item.volume, Decimal("12"))

    def test_reject_unsupported_type(self):
        bad = SimpleUploadedFile("data.csv", b"a,b,c\n", content_type="text/csv")
        with self.assertRaises(UnsupportedFileError):
            ExcelImporter().import_file(bad)

class HeaderMapperTests(TestCase):
    def test_maps_clean_headers(self):
        headers = ["No", "Uraian Pekerjaan", "Volume", "Satuan"]
        mapping, missing, originals = map_headers(headers)
        self.assertIn("number", mapping)
        self.assertIn("description", mapping)
        self.assertIn("volume", mapping)
        self.assertIn("unit", mapping)
        self.assertEqual(missing, [])
        self.assertEqual(originals["description"], "Uraian Pekerjaan")

    def test_maps_with_punctuation_and_case(self):
        headers = ["No.", "URAIAN", "VOL.", "satuan "]
        mapping, missing, _ = map_headers(headers)
        self.assertTrue(set(["number", "description", "volume", "unit"]).issubset(mapping.keys()))
        self.assertEqual(missing, [])

    def test_reports_missing_required(self):
        headers = ["No", "Deskripsi"]  # missing volume & satuan
        _, missing, _ = map_headers(headers)
        self.assertIn("volume", missing)
        self.assertIn("unit", missing)

    def test_find_header_row_skips_title_block(self):
        rows = [
            ["PEKERJAAN", None, ":", "PEMBANGUNAN"],  # fake title
            [None, None, None],
            ["No.", "URAIAN PEKERJAAN", "VOL.", "SATUAN"],  # real header
            ["1", "Bata Merah", "10", "m"],
        ]
        idx = find_header_row(rows, scan_first=10)
        self.assertEqual(idx, 2)  # 0-based index

class RabParserTests(TestCase):
    def setUp(self):
        """Set up test dependencies and sample project"""
        self.parser = create_rab_parser()
        self.project = Project.objects.create(
            program="TEST PROGRAM",
            kegiatan="TEST ACTIVITY",
            pekerjaan="TEST JOB",
            lokasi="TEST LOCATION",
            tahun_anggaran=2025
        )

    def test_cell_with_non_breaking_space_is_parsed_as_none(self):
        self.assertIsNone(self.parser.clean_cell("\u00A0"))
        self.assertIsNone(self.parser.clean_cell(" \u00A0 "))

    def test_converts_currency_string_with_rp_to_decimal(self):
        self.assertEqual(self.parser.to_decimal("Rp 5.000"), Decimal("5000"))

    def test_converts_number_with_indonesian_format_to_decimal(self):
        self.assertEqual(self.parser.to_decimal("1.234.567,89"), Decimal("1234567.89"))

    def test_converts_us_format_with_commas_to_decimal(self):
        self.assertEqual(self.parser.to_decimal("1,234,567.89"), Decimal("1234567.89"))

    def test_converts_percentage_format_to_decimal(self):
        result = self.parser.to_percentage("75%")
        self.assertEqual(result, Decimal("0.75"))

    def test_converts_boolean_strings_true(self):
        self.assertTrue(self.parser.to_boolean("TRUE"))
        self.assertTrue(self.parser.to_boolean("true"))
        self.assertTrue(self.parser.to_boolean("True"))

    def test_converts_boolean_strings_false(self):
        self.assertFalse(self.parser.to_boolean("FALSE"))
        self.assertFalse(self.parser.to_boolean("false"))
        self.assertFalse(self.parser.to_boolean("False"))

    def test_converts_date_string(self):
        result = self.parser.to_date("2024-12-31")
        self.assertEqual(result, date(2024, 12, 31))

    def test_converts_indonesian_date_format(self):
        result = self.parser.to_date("31/12/2024")
        self.assertEqual(result, date(2024, 12, 31))

    def test_handles_scientific_notation_string(self):
        self.assertEqual(self.parser.to_decimal("1.23E+5"), Decimal("123000"))

    def test_row_with_mixed_data_types_parsed_correctly(self):
        raw_row = {
            'No.': '5', 'URAIAN PEKERJAAN': 'Mixed Data Item',
            'VOL.': '2.50', 'HARGA SATUAN (Rp.)': '1.000.000,50'
        }
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.item_number, '5')
        self.assertEqual(entry.volume, Decimal('2.50'))
        self.assertEqual(entry.unit_price, Decimal('1000000.50'))

    def test_validates_required_fields(self):
        raw_row = {'No.': '6', 'URAIAN PEKERJAAN': '', 'VOL.': '1.00'}
        result = self.parser.parse_row(raw_row, project=self.project)
        self.assertIsNone(result)

    def test_processes_all_cells_for_data_type_conversion(self):
        raw_row = {
            'No.': ' 1 ', 'URAIAN PEKERJAAN': '  Test\nItem  ', 'SATUAN': ' Ls ',
            'KODE ANALISA': '  AT.19-1  ', 'VOL.': ' 2,50 ',
            'HARGA SATUAN (Rp.)': ' Rp 1.000.000 ', 'JUMLAH HARGA (Rp.)': ' 2.500.000,00 '
        }
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.item_number, '1')
        self.assertEqual(entry.description, 'Test Item')
        self.assertEqual(entry.unit, 'Ls')
        self.assertEqual(entry.analysis_code, 'AT.19-1')
        self.assertEqual(entry.volume, Decimal('2.50'))
        self.assertEqual(entry.unit_price, Decimal('1000000'))
        self.assertEqual(entry.total_price, Decimal('2500000.00'))

    def test_parses_row_with_total_in_words(self):
        raw_row = {'URAIAN PEKERJAAN': 'Terbilang : Seratus Juta Rupiah'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.GRAND_TOTAL)
        self.assertEqual(entry.total_price_in_words, "Seratus Juta Rupiah")