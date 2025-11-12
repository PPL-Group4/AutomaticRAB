from django.test import TestCase
from excel_parser.services import header_mapper


class HeaderMapperTests(TestCase):
    def test_map_headers_all_found(self):
        headers = ["No", "Uraian Pekerjaan", "Volume", "Satuan"]
        mapping, missing, originals = header_mapper.map_headers(headers)
        self.assertIn("no", mapping)
        self.assertIn("uraian", mapping)
        self.assertIn("volume", mapping)
        self.assertIn("satuan", mapping)
        self.assertEqual(missing, [])
        self.assertEqual(originals["uraian"], "Uraian Pekerjaan")

    def test_map_headers_with_punctuation_and_case(self):
        headers = ["NO.", "URAIAN ", "VOL.", "SATUAN "]
        mapping, missing, _ = header_mapper.map_headers(headers)
        self.assertTrue(all(k in mapping for k in ("no", "uraian", "volume", "satuan")))
        self.assertEqual(missing, [])

    def test_map_headers_missing_required_logs_warning(self):
        headers = ["No", "Deskripsi"]  # missing volume & satuan
        with self.assertLogs("excel_parser", level="WARNING") as cm:
            mapping, missing, _ = header_mapper.map_headers(headers)
        self.assertIn("missing_required", cm.output[0])
        self.assertIn("volume", missing)
        self.assertIn("satuan", missing)
        self.assertEqual(list(mapping.keys()), ["no", "uraian"])

    def test_find_header_row_finds_best_match(self):
        rows = [
            ["TITLE", "PROJECT"],
            ["No", "Uraian Pekerjaan", "Volume", "Satuan"],
            ["1", "Pekerjaan A", "2", "m2"]
        ]
        idx = header_mapper.find_header_row(rows)
        self.assertEqual(idx, 1)

    def test_find_header_row_handles_no_match_returns_first(self):
        rows = [["A", "B"], ["X", "Y"]]
        idx = header_mapper.find_header_row(rows)
        self.assertEqual(idx, 0)

    def test_normalize_removes_accents_and_symbols(self):
        text = "  Nómôr: 01/A-1  "
        result = header_mapper._normalize(text)
        self.assertEqual(result, "nomor 01 a 1")

    def test_normalize_handles_none_and_blank(self):
        self.assertEqual(header_mapper._normalize(None), "")
        self.assertEqual(header_mapper._normalize("   "), "")
