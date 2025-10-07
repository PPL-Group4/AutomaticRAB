from io import BytesIO
from decimal import Decimal
import tempfile
from django.core.exceptions import ValidationError
from excel_parser.services.header_mapper import map_headers, find_header_row
from excel_parser.services.validators import validate_excel_file
from excel_parser.services.services import ExcelSniffer
from excel_parser.services import create_rab_parser
from excel_parser.services.reader import ExcelImporter, UnsupportedFileError
from excel_parser.services import reader as reader_mod
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,Client
from openpyxl import Workbook
from rest_framework.test import APITestCase
from excel_parser.services.reader import preview_file
from django.apps import apps
from django.db import connection,models
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile



from excel_parser.models import Project, RabEntry

from excel_parser.services.reader import ExcelImporter
from rencanakan_core.models import RabItem, Rab

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
        file = SimpleUploadedFile(
            "dummy.doc",
            b"fake word",
            content_type="application/msword",
        )
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
        file = SimpleUploadedFile(
            "dummy.ppt",
            b"fake ppt",
            content_type="application/vnd.ms-powerpoint",
        )
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
        file = SimpleUploadedFile(
            "dummy.csv",
            b"a,b,c\n1,2,3",
            content_type="text/csv",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_image_file(self):
        file = SimpleUploadedFile(
            "image.jpg",
            b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_png_file(self):
        file = SimpleUploadedFile(
            "image.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_gif_file(self):
        file = SimpleUploadedFile(
            "image.gif",
            b"GIF89a",
            content_type="image/gif",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

    def test_rejects_zip_file(self):
        file = SimpleUploadedFile(
            "archive.zip",
            b"PK\x03\x04",
            content_type="application/zip",
        )
        with self.assertRaises(ValidationError):
            validate_excel_file(file)

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
        self.assertIn("no", mapping)
        self.assertIn("uraian", mapping)
        self.assertIn("volume", mapping)
        self.assertIn("satuan", mapping)
        self.assertEqual(missing, [])
        self.assertEqual(originals["uraian"], "Uraian Pekerjaan")

    def test_maps_with_punctuation_and_case(self):
        headers = ["No.", "URAIAN", "VOL.", "satuan "]
        mapping, missing, _ = map_headers(headers)
        self.assertTrue(set(["no", "uraian", "volume", "satuan"]).issubset(mapping.keys()))
        self.assertEqual(missing, [])

    def test_reports_missing_required(self):
        headers = ["No", "Deskripsi"]  # missing volume & satuan
        _, missing, _ = map_headers(headers)
        self.assertIn("volume", missing)
        self.assertIn("satuan", missing)

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
        self.parser = create_rab_parser()  # Uses factory with proper DI
        self.project = Project.objects.create(
            program="TEST PROGRAM",
            kegiatan="TEST ACTIVITY",
            pekerjaan="TEST JOB",
            lokasi="TEST LOCATION",
            tahun_anggaran=2025
        )

    def test_trims_leading_and_trailing_whitespace(self):
        self.assertEqual(self.parser.clean_cell("  Some Text  "), "Some Text")

    def test_collapses_multiple_internal_spaces(self):
        self.assertEqual(self.parser.clean_cell("Text   with    extra spaces"), "Text with extra spaces")

    def test_replaces_newline_with_space(self):
        self.assertEqual(self.parser.clean_cell("Line one\nLine two"), "Line one Line two")

    def test_empty_and_whitespace_cell_is_parsed_as_none(self):
        self.assertIsNone(self.parser.clean_cell(""))
        self.assertIsNone(self.parser.clean_cell("   "))

    def test_cell_with_non_breaking_space_is_parsed_as_none(self):
        self.assertIsNone(self.parser.clean_cell("\u00A0"))
        self.assertIsNone(self.parser.clean_cell(" \u00A0 "))

    def test_converts_standard_numeric_string_to_decimal(self):
        self.assertEqual(self.parser.to_decimal("1234.56"), Decimal("1234.56"))

    def test_converts_number_to_integer(self):
        self.assertEqual(self.parser.to_decimal("123"), Decimal("123"))

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

    def test_handles_large_numbers_without_crashing(self):
        self.assertEqual(self.parser.to_decimal("99.999.999.999,00"), Decimal("99999999999.00"))

    def test_handles_overflow_numbers_safely(self):
        result = self.parser.to_decimal("999999999999999999999999999999")
        self.assertIsInstance(result, Decimal)

    def test_handles_scientific_notation_string(self):
        self.assertEqual(self.parser.to_decimal("1.23E+5"), Decimal("123000"))

    def test_returns_none_for_invalid_numeric_string(self):
        self.assertIsNone(self.parser.to_decimal("12abc"))
        self.assertIsNone(self.parser.to_decimal("N/A"))

    def test_returns_none_for_empty_or_none_input(self):
        self.assertIsNone(self.parser.to_decimal(None))
        self.assertIsNone(self.parser.to_decimal(""))

    def test_handles_mixed_data_in_numeric_column(self):
        self.assertEqual(self.parser.clean_cell("N/A"), "N/A")
        self.assertIsNone(self.parser.to_decimal("N/A"))

    def test_parses_clean_row_and_creates_item_entry(self):
        raw_row = {
            'No.': '1', 'URAIAN PEKERJAAN': 'Mobilisasi/demobilisasi', 'SATUAN': 'Ls',
            'KODE ANALISA': 'AT.19-1', 'VOL.': '1,00', 'HARGA SATUAN (Rp.)': '1.500.000',
            'JUMLAH HARGA (Rp.)': '1.500.000'
        }
        parent_section = RabEntry.objects.create(
            project=self.project, entry_type=RabEntry.EntryType.SECTION, description="Parent"
        )
        entry = self.parser.parse_row(raw_row, project=self.project, parent=parent_section)

        self.assertEqual(entry.entry_type, RabEntry.EntryType.ITEM)
        self.assertEqual(entry.item_number, '1')
        self.assertEqual(entry.description, 'Mobilisasi/demobilisasi')
        self.assertEqual(entry.volume, Decimal('1.00'))
        self.assertEqual(entry.total_price, Decimal('1500000'))
        self.assertEqual(entry.parent, parent_section)

    def test_row_with_missing_middle_cell_is_parsed_with_null(self):
        raw_row = {'No.': '2', 'URAIAN PEKERJAAN': 'Test Item', 'VOL.': '5.00', 'SATUAN': None}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertIsNone(entry.unit)
        self.assertEqual(entry.volume, Decimal('5.00'))

    def test_row_with_only_whitespace_is_skipped(self):
        raw_row = {'No.': '   ', 'URAIAN PEKERJAAN': ' ', 'VOL.': None}
        self.assertIsNone(self.parser.parse_row(raw_row, project=self.project))

    def test_parses_row_with_extra_columns_gracefully(self):
        raw_row = {'No.': '3', 'URAIAN PEKERJAAN': 'Extra Item', 'EXTRA_COLUMN': 'ignored'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.description, 'Extra Item')

    def test_row_with_fewer_columns_pads_with_null(self):
        raw_row = {'No.': '4', 'URAIAN PEKERJAAN': 'Incomplete Item'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertIsNone(entry.volume)
        self.assertIsNone(entry.unit)

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

    def test_handles_file_with_only_headers(self):
        initial_count = RabEntry.objects.count()
        row_list = []
        for row in row_list:
            self.parser.parse_row(row, self.project)
        self.assertEqual(RabEntry.objects.count(), initial_count)

    def test_processes_all_cells_for_data_type_conversion(self):
        raw_row = {
            'No.': ' 1 ', 'URAIAN PEKERJAAN': '  Test\nItem  ', 'SATUAN': ' Ls ',
            'KODE ANALISA': '  AT.19-1  ', 'VOL.': ' 2,50 ',
            'HARGA SATUAN (Rp.)': ' Rp 1.000.000 ', 'JUMLAH HARGA (Rp.)': ' 2.500.000,00 '
        }
        entry = self.parser.parse_row(raw_row, project=self.project)

        self.assertEqual(entry.item_number, '1')  # Trimmed
        self.assertEqual(entry.description, 'Test Item')  # Newline replaced, trimmed
        self.assertEqual(entry.unit, 'Ls')  # Trimmed
        self.assertEqual(entry.analysis_code, 'AT.19-1')  # Trimmed
        self.assertEqual(entry.volume, Decimal('2.50'))  # Indonesian format converted
        self.assertEqual(entry.unit_price, Decimal('1000000'))  # Currency converted
        self.assertEqual(entry.total_price, Decimal('2500000.00'))  # Indonesian format converted

    def test_preserves_na_values_for_manual_input(self):
        raw_row = {
            'No.': '1', 'URAIAN PEKERJAAN': 'N/A requires manual input',
            'SATUAN': 'N/A', 'KODE ANALISA': 'TBD'
        }
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.unit, 'N/A')
        self.assertEqual(entry.analysis_code, 'TBD')

    def test_classifies_row_as_site_header(self):
        raw_row = {'URAIAN PEKERJAAN': 'BUJAK 1', 'No.': None}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.SITE_HEADER)
        self.assertEqual(entry.description, "BUJAK 1")

    def test_classifies_row_as_main_section(self):
        raw_row = {'No.': 'A', 'URAIAN PEKERJAAN': 'PEMBUATAN SUMUR BOR'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.SECTION)

    def test_classifies_row_as_sub_section(self):
        raw_row = {'No.': 'I', 'URAIAN PEKERJAAN': 'PEKERJAAN PERSIAPAN'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.SUB_SECTION)

    def test_classifies_row_as_sub_total(self):
        raw_row = {'URAIAN PEKERJAAN': 'Sub Total Pekerjaan Persiapan', 'JUMLAH HARGA (Rp.)': '5.000.000'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.SUB_TOTAL)
        self.assertEqual(entry.total_price, Decimal('5000000'))

    def test_classifies_row_as_grand_total(self):
        raw_row = {'URAIAN PEKERJAAN': 'Total Biaya', 'JUMLAH HARGA (Rp.)': '125.000.000'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.SUB_TOTAL)

    def test_parses_row_with_total_in_words(self):
        raw_row = {'URAIAN PEKERJAAN': 'Terbilang : Seratus Juta Rupiah'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.GRAND_TOTAL)
        self.assertEqual(entry.total_price_in_words, "Seratus Juta Rupiah")

    def test_parses_comment_or_descriptive_row_as_item(self):
        raw_row = {'URAIAN PEKERJAAN': 'Pekerjaan dilaksanakan Sesuai Spek'}
        entry = self.parser.parse_row(raw_row, project=self.project)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.ITEM)
        self.assertIsNone(entry.volume)

class ReaderPrivateHelpersTests(TestCase):
    def test__norm_and__match_header(self):
        self.assertEqual(reader_mod._norm("  No.  "), "no.")
        key, raw = reader_mod._match_header("Uraian")
        self.assertEqual(key, "description")
        self.assertEqual(raw, "Uraian")
        key2, raw2 = reader_mod._match_header("Satuan")
        self.assertEqual(key2, "unit")
        self.assertEqual(raw2, "Satuan")

    def test_parse_decimal_full_branches(self):
        from excel_parser.services import reader as reader_mod

        # invalid numeric strings should just return 0 instead of crashing
        self.assertEqual(reader_mod.parse_decimal("not_a_number"), Decimal("0"))
        self.assertEqual(reader_mod.parse_decimal("7 = 5 x 6"), Decimal("0"))

    def test_parse_decimal_branch_last_separator_logic(self):
        # Case 1: last comma after dot -> koma decimal
        self.assertEqual(reader_mod.parse_decimal("1.234,56"), Decimal("1234.56"))
        # Case 2: last dot after comma -> dot decimal
        self.assertEqual(reader_mod.parse_decimal("1,234.56"), Decimal("1234.56"))

    def test__ext_of_and_make_reader_and_unsupported(self):
        good_xlsx = SimpleUploadedFile("a.xlsx", b"data")
        self.assertEqual(reader_mod._ext_of(good_xlsx), "xlsx")
        r = reader_mod.make_reader(good_xlsx)
        self.assertIsInstance(r, reader_mod._XLSXReader)

        bad = SimpleUploadedFile("a.csv", b"a,b\n")
        self.assertEqual(reader_mod._ext_of(bad), "")
        with self.assertRaises(reader_mod.UnsupportedFileError):
            reader_mod.make_reader(bad)

    def test__base_reader_iter_rows_raises(self):
        base = reader_mod._BaseReader()
        with self.assertRaises(NotImplementedError):
            list(base.iter_rows(SimpleUploadedFile("x.xlsx", b"")))

    def test_parse_decimal_last_separator_fallback_irregular_grouping(self):
        self.assertEqual(reader_mod.parse_decimal("12.34,56"), Decimal("1234.56"))
        self.assertEqual(reader_mod.parse_decimal("1.2.3,4"),   Decimal("123.4"))

        self.assertEqual(reader_mod.parse_decimal("12,34.56"), Decimal("1234.56"))
        self.assertEqual(reader_mod.parse_decimal("1,2,3.4"),  Decimal("123.4"))

class ReaderHeaderAndRowParsingTests(TestCase):
    def test__find_header_map_success_with_preface(self):
        rows = [
            ["Judul", "Meta"],
            [None, None],
            ["No.", "Uraian Pekerjaan", "Volume", "Satuan"],
            ["1", "Item A", "1,5", "pcs"],
        ]
        colmap, hdr = reader_mod._find_header_map(rows)
        self.assertEqual(hdr, 2)
        for k in ("number", "description", "volume", "unit"):
            self.assertIn(k, colmap)

    def test__find_header_map_missing_raises(self):
        rows = [
            ["Random", "Header"],
            ["Kode", "Deskripsi"],
            ["1", "A"],
        ]
        with self.assertRaises(reader_mod.ParseError):
            reader_mod._find_header_map(rows)

    def test__rows_after(self):
        cache = [
            ["No", "Uraian", "Volume", "Satuan"],
            ["1", "A", "10", "m"],
            ["2", "B", "20", "m"],
        ]
        out = list(reader_mod._rows_after(cache, start_idx=0))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "1")
        self.assertEqual(out[1][1], "B")

    def test__parse_rows_skip_empty_and_cast(self):
        cache = [
            ["No", "Uraian", "Volume", "Satuan"],  # header index 0
            ["1", "Item A", "1.000,50", "m3"],
            ["", "", "", ""],                      # empty -> skip
            ["2", "Item B", "2,5", "m3"],
        ]
        colmap = {"number": 0, "description": 1, "volume": 2, "unit": 3, "_header_row": 0}
        parsed = reader_mod._parse_rows(cache, colmap)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].number, "1")
        self.assertEqual(parsed[0].description, "Item A")
        self.assertEqual(parsed[0].volume, Decimal("1000.50"))
        self.assertEqual(parsed[0].unit, "m3")
        self.assertEqual(parsed[1].volume, Decimal("2.5"))


class ImporterDefaultsTests(TestCase):
    def test_importer_sets_project_defaults_and_enum_and_count(self):
        bio = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan"])
        ws.append(["1", "Gali tanah", "1.000,50", "m3"])
        ws.append(["2", "Urug tanah", "250", "m3"])
        wb.save(bio)
        f = SimpleUploadedFile(
            "mini.xlsx",
            bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        count = ExcelImporter().import_file(f)
        self.assertEqual(count, 2)

        proj = Project.objects.get()
        self.assertEqual(proj.program, "Default Program")
        self.assertEqual(proj.kegiatan, "Default Activity")
        self.assertEqual(proj.pekerjaan, "Imported from Excel")
        self.assertEqual(proj.lokasi, "Not Specified")
        self.assertEqual(proj.tahun_anggaran, 2025)

        self.assertEqual(RabEntry.objects.count(), 2)
        e1 = RabEntry.objects.order_by("row_index").first()
        self.assertEqual(e1.item_number, "1")
        self.assertEqual(e1.description, "Gali tanah")
        self.assertEqual(e1.volume, Decimal("1000.50"))
        self.assertEqual(e1.unit, "m3")
        self.assertEqual(e1.entry_type, RabEntry.EntryType.ITEM)
class PreviewFileTests(APITestCase):
    def test_preview_file_includes_all_columns(self):
        # Build Excel file in memory
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Jumlah Harga"])
        ws.append(["1", "Gali tanah", "1000", "m3", "25000", "25000000"])
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        f = SimpleUploadedFile(
            "mini.xlsx",
            bio.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            "/excel_parser/preview_rows",
            {"excel_standard": f},   # ✅ matches the view
            format="multipart"
        )

        self.assertEqual(response.status_code, 200, response.content)

        # ✅ unwrap the actual key your view uses
        rows = response.json()["excel_standard"]

        self.assertIn("analysis_code", rows[0])
        self.assertIn("price", rows[0])
        self.assertIn("total_price", rows[0])


    def test_preview_file_detects_section_rows(self):
                # Build an in-memory Excel file
                bio = BytesIO()
                wb = Workbook()
                ws = wb.active
                ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Jumlah Harga"])
                ws.append(["I.", "PEKERJAAN PERSIAPAN", "", ""])  # should be a section
                ws.append(["1", "Mobilisasi", "1", "Ls", "1000", "1000"])  # should be an item
                wb.save(bio)

                f = SimpleUploadedFile(
                    "mini.xlsx",
                    bio.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                rows = preview_file(f)
                # Check first row is section
                self.assertTrue(rows[0]["is_section"])
                self.assertEqual(rows[0]["description"], "PEKERJAAN PERSIAPAN")

                # Check second row is normal item
                self.assertFalse(rows[1]["is_section"])
                self.assertEqual(rows[1]["description"], "Mobilisasi")
                self.assertAlmostEqual(float(rows[1]["volume"]), 1.0, places=2)
                self.assertEqual(rows[1]["price"], "1000.00")
                self.assertEqual(rows[1]["total_price"], "1000.00")



class TestProject(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "test_projects"
        managed = True


class TestRab(models.Model):
    name = models.CharField(max_length=255)
    project = models.ForeignKey(TestProject, on_delete=models.CASCADE)

    class Meta:
        db_table = "test_rabs"
        managed = True
from django.db import connection
class TestRabItemHeader(models.Model):
    rab = models.ForeignKey(TestRab, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "test_rab_item_headers"
        managed = True


class TestRabItem(models.Model):
    rab = models.ForeignKey(TestRab, on_delete=models.CASCADE, null=True)
    rab_item_header = models.ForeignKey(TestRabItemHeader, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=500, null=True)
    volume = models.FloatField(null=True)
    price = models.FloatField(null=True)
    unit = models.CharField(max_length=50, null=True)

    class Meta:
        db_table = "test_rab_items"
        managed = True

from django.test import TransactionTestCase
from django.db import connection

class ImporterIntegrationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # manually create test tables
        with connection.schema_editor() as schema:
            schema.create_model(TestProject)
            schema.create_model(TestRab)
            schema.create_model(TestRabItemHeader)
            schema.create_model(TestRabItem)

    @classmethod
    def tearDownClass(cls):
        # clean up tables
        with connection.schema_editor() as schema:
            schema.delete_model(TestRabItem)
            schema.delete_model(TestRabItemHeader)
            schema.delete_model(TestRab)
            schema.delete_model(TestProject)
        super().tearDownClass()

    def test_importer_inserts_into_rab_items(self):
        project = TestProject.objects.create(name="Test Project")
        rab = TestRab.objects.create(name="Test RAB", project=project)

        # build a tiny Excel file
        bio = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Jumlah Harga"])
        ws.append(["1", "Mobilisasi", "1", "Ls", "1000", "1000"])
        wb.save(bio)

        f = SimpleUploadedFile(
            "mini.xlsx", bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        from excel_parser.services.reader import preview_file
        rows = preview_file(f)

        # simulate writing into TestRabItem
        for row in rows:
            TestRabItem.objects.create(
                rab=rab,
                name=row["description"],
                volume=row["volume"],
                price=row["price"],
                unit=row["unit"]
            )

        self.assertEqual(TestRabItem.objects.count(), 1)
        item = TestRabItem.objects.first()
        self.assertEqual(item.name, "Mobilisasi")
        self.assertEqual(item.volume, 1.0)
        self.assertEqual(item.price, 1000.0)

class RABConvertedViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_rab_converted_page_loads(self):
        response = self.client.get("/excel_parser/rab_converted/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "rab_converted.html")

class LoggingTests(TestCase):
    def _make_excel_file(self, filename="logtest.xlsx"):
        bio = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan"])
        ws.append([1, "Test pekerjaan", 10, "m2"])
        wb.save(bio)
        return SimpleUploadedFile(
            filename, bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_import_file_logs(self):
        f = self._make_excel_file()
        importer = ExcelImporter()

        with self.assertLogs("excel_parser", level="INFO") as cm:
            importer.import_file(f)

        logs = "\n".join(cm.output)
        self.assertIn("Starting import", logs)
        self.assertIn("Import finished", logs)

    def test_preview_file_logs(self):
        f = self._make_excel_file()

        with self.assertLogs("excel_parser", level="INFO") as cm:
            preview_file(f)

        logs = "\n".join(cm.output)
        self.assertIn("Previewing file", logs)
        self.assertIn("Preview parsed", logs)

    def test_validator_logs_warning(self):
        bad_file = SimpleUploadedFile("bad.txt", b"not excel", content_type="text/plain")

        with self.assertLogs("excel_parser", level="WARNING") as cm:
            with self.assertRaises(ValidationError):
                validate_excel_file(bad_file)

        logs = "\n".join(cm.output)
        self.assertIn("Rejected file", logs)
