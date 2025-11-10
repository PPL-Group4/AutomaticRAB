from django.test import TestCase
from pdf_parser.services.row_parser import PdfRowParser, ParsedRow
from pdf_parser.services.header_mapper import TextFragment


class PdfRowParserUnitTests(TestCase):
    def setUp(self):
        # Keep defaults; relies on PdfHeaderMapper's recognition of common headers
        self.parser = PdfRowParser()

    # ===== Helpers =====
    def _headers_at(self, page: int, y: float, xs=None):
        """
        Return standard header fragments ("No", "Uraian Pekerjaan", "Volume", "Satuan")
        placed left-to-right at given y and x positions.
        """
        if xs is None:
            xs = [10, 120, 260, 360]
        return [
            TextFragment(page=page, x=xs[0], y=y, text="No"),
            TextFragment(page=page, x=xs[1], y=y, text="Uraian Pekerjaan"),
            TextFragment(page=page, x=xs[2], y=y, text="Volume"),
            TextFragment(page=page, x=xs[3], y=y, text="Satuan"),
        ]

    def _row(self, page: int, y: float, no="1", uraian="Pekerjaan A", volume="10", satuan="m2", xs=None):
        if xs is None:
            xs = [10, 120, 260, 360]
        return [
            TextFragment(page=page, x=xs[0], y=y, text=str(no)),
            TextFragment(page=page, x=xs[1], y=y, text=str(uraian)),
            TextFragment(page=page, x=xs[2], y=y, text=str(volume)),
            TextFragment(page=page, x=xs[3], y=y, text=str(satuan)),
        ]

    def test_compute_x_boundaries_ordering(self):
        headers = {
            "no": TextFragment(page=1, x=10, y=100, text="No"),
            "uraian": TextFragment(page=1, x=120, y=100, text="Uraian Pekerjaan"),
            "volume": TextFragment(page=1, x=260, y=100, text="Volume"),
            "satuan": TextFragment(page=1, x=360, y=100, text="Satuan"),
        }
        boundaries = self.parser._compute_x_boundaries(headers)
        # First column xmin=-inf, last xmax=+inf, mids between 10/120, 120/260, 260/360
        self.assertIn("no", boundaries)
        self.assertIn("uraian", boundaries)
        self.assertIn("volume", boundaries)
        self.assertIn("satuan", boundaries)

        no_min, no_max = boundaries["no"]
        ura_min, ura_max = boundaries["uraian"]
        vol_min, vol_max = boundaries["volume"]
        sat_min, sat_max = boundaries["satuan"]

        self.assertTrue(no_min < -1e8 and sat_max > 1e8)  # -inf / +inf emulation
        self.assertLessEqual(no_max, ura_min)
        self.assertLessEqual(ura_max, vol_min)
        self.assertLessEqual(vol_max, sat_min)

    def test_group_by_y_merges_close_rows_and_sorts_by_x(self):
        p = PdfRowParser(y_bucket_precision=0, y_tolerance=0.8)
        # Two fragments around same y within tolerance should be grouped
        frags = [
            TextFragment(page=1, x=100, y=150.4, text="A"),
            TextFragment(page=1, x=120, y=150.49, text="B"),  # within tolerance
            TextFragment(page=1, x=90,  y=170.3, text="C"),
        ]
        groups = p._group_by_y(frags)
        # Expect two row buckets
        self.assertEqual(len(groups), 2)
        # Each group's fragments are sorted by x
        for _, g in groups:
            xs = [f.x for f in g]
            self.assertEqual(xs, sorted(xs))

    def test_assign_to_columns_basic(self):
        headers = {
            "no": TextFragment(page=1, x=10, y=100, text="No"),
            "uraian": TextFragment(page=1, x=120, y=100, text="Uraian Pekerjaan"),
            "volume": TextFragment(page=1, x=260, y=100, text="Volume"),
            "satuan": TextFragment(page=1, x=360, y=100, text="Satuan"),
        }
        boundaries = self.parser._compute_x_boundaries(headers)
        row_frags = self._row(page=1, y=130)
        cells = self.parser._assign_to_columns(row_frags, boundaries, headers)
        self.assertTrue(all(k in cells for k in ["no", "uraian", "volume", "satuan"]))
        self.assertEqual(len(cells["no"]), 1)
        self.assertEqual(len(cells["uraian"]), 1)
        self.assertEqual(len(cells["volume"]), 1)
        self.assertEqual(len(cells["satuan"]), 1)

    def test_assign_to_columns_roman_section_stays_in_description(self):
        headers = {
            "uraian": TextFragment(page=1, x=62.8, y=100, text="Jenis Barang/Jasa"),
            "satuan": TextFragment(page=1, x=294.9, y=100, text="Satuan Unit"),
            "volume": TextFragment(page=1, x=410.9, y=100, text="Volume"),
        }
        boundaries = self.parser._compute_x_boundaries(headers)
        row_frags = [
            TextFragment(page=1, x=63.0, y=130, text="I.Rencana"),
            TextFragment(page=1, x=117.5, y=130, text="Keselamatan"),
            TextFragment(page=1, x=190.3, y=130, text="Konstruksi"),
        ]

        cells = self.parser._assign_to_columns(row_frags, boundaries, headers)

        self.assertEqual([f.text for f in cells["uraian"]], ["I.Rencana", "Keselamatan", "Konstruksi"])
        self.assertEqual(cells["satuan"], [])

    def test_merge_cell_text_joins_and_strips(self):
        frags = [
            TextFragment(page=1, x=120, y=130, text="Pekerjaan"),
            TextFragment(page=1, x=150, y=130, text="A "),
            TextFragment(page=1, x=300, y=130, text="(lanjutan)"),
        ]
        merged = self.parser._merge_cell_text(frags)
        self.assertEqual(merged, "Pekerjaan A (lanjutan)")

    def test_parse_single_page_two_rows(self):
        fragments = []
        fragments += self._headers_at(page=1, y=100)
        fragments += self._row(page=1, y=110, no="1", uraian="Pekerjaan A", volume="10", satuan="m2")
        fragments += self._row(page=1, y=130, no="2", uraian="Pekerjaan B", volume="5", satuan="m")

        rows, boundaries = self.parser.parse(fragments)
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows[0], ParsedRow)
        self.assertEqual(rows[0].values["no"], "1")
        self.assertEqual(rows[0].values["uraian"], "Pekerjaan A")
        self.assertEqual(rows[0].values["volume"], "10")
        self.assertEqual(rows[0].values["satuan"], "m2")
        self.assertEqual(rows[1].values["no"], "2")
        self.assertTrue("no" in boundaries and "uraian" in boundaries)

    def test_parse_skips_rows_too_close_to_header(self):
        fragments = []
        fragments += self._headers_at(page=1, y=100)
        fragments += self._row(page=1, y=104, no="1", uraian="ShouldSkip", volume="9", satuan="m2")
        fragments += self._row(page=1, y=120, no="2", uraian="ShouldStay", volume="3", satuan="m2")

        rows, _ = self.parser.parse(fragments)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].values["no"], "2")
        self.assertEqual(rows[0].values["uraian"], "ShouldStay")

    def test_parse_multi_page_and_last_boundaries_returned(self):
        fragments = []
        fragments += self._headers_at(page=1, y=90)
        fragments += self._row(page=1, y=110, no="1", uraian="P1", volume="1", satuan="m")
        fragments += self._headers_at(page=2, y=80, xs=[20, 180, 300, 420])
        fragments += self._row(page=2, y=100, no="2", uraian="P2", volume="2", satuan="kg", xs=[20, 180, 300, 420])

        rows, last_boundaries = self.parser.parse(fragments)
        self.assertEqual([(r.page, r.values["no"]) for r in rows], [(1, "1"), (2, "2")])
        self.assertIn("uraian", last_boundaries)
        ura_min, ura_max = last_boundaries["uraian"]
        self.assertLess(ura_min, 180)
        self.assertGreater(ura_max, 180)

    def test_parse_reuses_headers_without_new_header_row(self):
        fragments = []
        fragments += self._headers_at(page=1, y=90)
        fragments += self._row(page=1, y=110, no="1", uraian="P1", volume="1", satuan="m")
        fragments += [
            TextFragment(page=2, x=10, y=35, text="2"),
            TextFragment(page=2, x=120, y=35, text="P2"),
            TextFragment(page=2, x=260, y=35, text="2"),
            TextFragment(page=2, x=360, y=35, text="kg"),
        ]
        rows, _ = self.parser.parse(fragments)
        numbers = [(r.page, r.values.get("no")) for r in rows]
        self.assertIn((1, "1"), numbers)
        self.assertIn((2, "2"), numbers)

    def test_parse_empty_or_no_headers(self):
        rows, bounds = self.parser.parse([])
        self.assertEqual(rows, [])
        self.assertEqual(bounds, {})
