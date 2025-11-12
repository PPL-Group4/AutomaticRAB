from decimal import Decimal
from django.test import TestCase
from pdf_parser.services.pipeline import merge_broken_rows


class PipelineHelperTests(TestCase):

    def test_merge_broken_rows_keeps_numbered_sections(self):
        rows = [
            {"number": "2", "description": "Sosialisasi, Promosi dan Pelatihan", "unit": "ls", "volume": Decimal("1"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
            {"number": "3", "description": "Alat Pelindung Kerja (APK), terdiri dari", "unit": "", "volume": Decimal("0"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
        ]

        merged = merge_broken_rows(rows)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["number"], "2")
        self.assertEqual(merged[1]["number"], "3")

    def test_merge_broken_rows_merges_numeric_fragment(self):
        rows = [
            {"number": "1", "description": "Pek. Pemasangan Lampu LED Downlight", "unit": "unit", "volume": Decimal("76"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
            {"number": "", "description": "23 Watt", "unit": "", "volume": Decimal("0"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
        ]

        merged = merge_broken_rows(rows)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["description"], "Pek. Pemasangan Lampu LED Downlight 23 Watt")

    def test_merge_broken_rows_merges_measurement_suffix(self):
        rows = [
            {"number": "6", "description": "Pek. Pemasangan Kaso Baja Ringan C75", "unit": "m", "volume": Decimal("1302.22"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
            {"number": "", "description": "tebal 0,75", "unit": "mm", "volume": Decimal("0"), "analysis_code": "", "price": Decimal("0"), "total_price": Decimal("0")},
        ]

        merged = merge_broken_rows(rows)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["description"], "Pek. Pemasangan Kaso Baja Ringan C75 tebal 0,75 mm")

    def test_merge_broken_rows_handles_word_fragment_number_column(self):
        rows = [
            {
                "number": "",
                "description": "Lantai 1, dipasang secara lengkap sesuai",
                "unit": "",
                "volume": Decimal("0"),
                "analysis_code": "",
                "price": Decimal("0"),
                "total_price": Decimal("0"),
            },
            {
                "number": "",
                "description": "di uraikan dalam gambar",
                "unit": "",
                "volume": Decimal("0"),
                "analysis_code": "",
                "price": Decimal("0"),
                "total_price": Decimal("0"),
            },
            {
                "number": "",
                "description": "dan spesifikasi teknis.",
                "unit": "",
                "volume": Decimal("0"),
                "analysis_code": "",
                "price": Decimal("0"),
                "total_price": Decimal("0"),
            },
        ]

        merged = merge_broken_rows(rows)

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged[0]["description"],
            "Lantai 1, dipasang secara lengkap sesuai di uraikan dalam gambar dan spesifikasi teknis.",
        )
