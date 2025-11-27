from django.test import TestCase

from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment


class PdfHeaderMapperEdgeCasesTests(TestCase):
    def setUp(self):
        self.mapper = PdfHeaderMapper()

    def _strip_optional(self, missing):
        optional = {"price", "total_price"}
        return [m for m in missing if m not in optional]

    # --- Positive / expected behavior ---

    def test_splits_header_across_fragments(self):
        fragments = [
            TextFragment(page=1, x=100, y=20, text="Uraian"),
            TextFragment(page=1, x=150, y=20, text="Pekerjaan"),
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, originals = self.mapper.map_headers(fragments)
        self.assertIn("uraian", mapping)
        self.assertEqual(originals["uraian"], "Uraian Pekerjaan")
        self.assertEqual(self._strip_optional(missing), [])

    def test_headers_out_of_order(self):
        fragments = [
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertTrue(set(["no", "uraian", "volume", "satuan"]).issubset(mapping.keys()))
        self.assertEqual(self._strip_optional(missing), [])

    def test_duplicate_header_fragments(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=12, y=20, text="No"),  # duplicate
            TextFragment(page=1, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertEqual(self._strip_optional(missing), [])
        self.assertIn("no", mapping)

    def test_headers_with_small_y_variation(self):
        fragments = [
            TextFragment(page=1, x=10, y=20.1, text="No"),
            TextFragment(page=1, x=100, y=19.9, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=200, y=20.05, text="Volume"),
            TextFragment(page=1, x=300, y=20.0, text="Satuan"),
        ]
        row_y = self.mapper.find_header_y(fragments)
        self.assertAlmostEqual(row_y, 20, delta=0.2)

    def test_headers_on_different_pages(self):
        fragments = [
            TextFragment(page=2, x=10, y=20, text="No"),
            TextFragment(page=2, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=2, x=200, y=20, text="Volume"),
            TextFragment(page=2, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertEqual(self._strip_optional(missing), [])

    def test_large_number_of_fragments(self):
        fragments = [
            TextFragment(page=1, x=i * 10, y=50, text=f"Noise{i}") for i in range(50)
        ] + [
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertEqual(self._strip_optional(missing), [])
        self.assertIn("uraian", mapping)

    # --- Negative / edge cases ---

    def test_empty_fragments(self):
        mapping, missing, _ = self.mapper.map_headers([])
        self.assertListEqual(self._strip_optional(missing), ["no", "uraian", "volume", "satuan"])
        self.assertDictEqual(mapping, {})

    def test_fragments_with_empty_text(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text=""),
            TextFragment(page=1, x=100, y=20, text="  "),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(self._strip_optional(missing), ["no", "uraian", "volume", "satuan"])
        self.assertDictEqual(mapping, {})

    def test_unrecognizable_headers(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text="Random1"),
            TextFragment(page=1, x=100, y=20, text="Random2"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(self._strip_optional(missing), ["no", "uraian", "volume", "satuan"])
        self.assertDictEqual(mapping, {})

    def test_fragments_with_none_or_whitespace(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text=None),
            TextFragment(page=1, x=100, y=20, text="   "),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(self._strip_optional(missing), ["no", "uraian", "volume", "satuan"])
        self.assertDictEqual(mapping, {})
