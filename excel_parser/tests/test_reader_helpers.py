from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from excel_parser.services import reader as reader_mod


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
        # invalid numeric strings should return 0 instead of crashing
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
        self.assertEqual(reader_mod.parse_decimal("1.2.3,4"), Decimal("123.4"))
        self.assertEqual(reader_mod.parse_decimal("12,34.56"), Decimal("1234.56"))
        self.assertEqual(reader_mod.parse_decimal("1,2,3.4"), Decimal("123.4"))


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
            ["No", "Uraian", "Volume", "Satuan"],
            ["1", "Item A", "1.000,50", "m3"],
            ["", "", "", ""],
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
