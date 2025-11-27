from datetime import date
from decimal import Decimal

from django.test import TestCase

from excel_parser.models import Project, RabEntry
from excel_parser.services import create_rab_parser


class RabParserTests(TestCase):
    def setUp(self):
        """Set up test dependencies and sample project"""
        self.parser = create_rab_parser()  # Factory returns parser with dependencies
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
        for val in ["TRUE", "true", "True"]:
            self.assertTrue(self.parser.to_boolean(val))

    def test_converts_boolean_strings_false(self):
        for val in ["FALSE", "false", "False"]:
            self.assertFalse(self.parser.to_boolean(val))

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
        for val in ["12abc", "N/A"]:
            self.assertIsNone(self.parser.to_decimal(val))

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
        parent = RabEntry.objects.create(
            project=self.project, entry_type=RabEntry.EntryType.SECTION, description="Parent"
        )
        entry = self.parser.parse_row(raw_row, project=self.project, parent=parent)
        self.assertEqual(entry.entry_type, RabEntry.EntryType.ITEM)
        self.assertEqual(entry.item_number, '1')
        self.assertEqual(entry.description, 'Mobilisasi/demobilisasi')
        self.assertEqual(entry.volume, Decimal('1.00'))
        self.assertEqual(entry.total_price, Decimal('1500000'))
        self.assertEqual(entry.parent, parent)

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
        self.assertEqual(entry.item_number, '1')
        self.assertEqual(entry.description, 'Test Item')
        self.assertEqual(entry.unit, 'Ls')
        self.assertEqual(entry.analysis_code, 'AT.19-1')
        self.assertEqual(entry.volume, Decimal('2.50'))
        self.assertEqual(entry.unit_price, Decimal('1000000'))
        self.assertEqual(entry.total_price, Decimal('2500000.00'))

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
