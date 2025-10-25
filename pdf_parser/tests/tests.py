import tempfile
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
import os
# import pytest
from pdf_parser.services.pdfreader import PdfReader,TextFragment

from pdf_parser.services.validators import validate_pdf_file
from pdf_parser.services.pdf_sniffer import PdfSniffer
from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment
from pdf_parser.services.row_parser import PdfRowParser, ParsedRow
from pdf_parser.services.normalizer import PdfRowNormalizer
from pdf_parser.services.pipeline import merge_broken_rows
from pdf_parser.services.header_mapper import TextFragment


class FileValidatorTests(TestCase):

    """Tests for extension and mimetype validation only"""

    def test_accepts_pdf_file(self):
        file = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        try:
            validate_pdf_file(file)
        except ValidationError:
            self.fail("Valid .pdf file was rejected")

    def test_empty_pdf_with_valid_mimetype(self):
        file = SimpleUploadedFile(
            "empty.pdf",
            b"",
            content_type="application/pdf",
        )
        try:
            validate_pdf_file(file)
        except ValidationError:
            self.fail("Empty but valid PDF file was rejected")

    def test_rejects_txt_file(self):
        file = SimpleUploadedFile("dummy.txt", b"hello", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_xlsx_file(self):
        file = SimpleUploadedFile(
            "dummy.xlsx",
            b"fake excel",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_xls_file(self):
        file = SimpleUploadedFile(
            "dummy.xls",
            b"fake excel",
            content_type="application/vnd.ms-excel",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_doc_file(self):
        file = SimpleUploadedFile(
            "dummy.doc",
            b"fake word",
            content_type="application/msword",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_docx_file(self):
        file = SimpleUploadedFile(
            "dummy.docx",
            b"fake word",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_ppt_file(self):
        file = SimpleUploadedFile(
            "dummy.ppt",
            b"fake ppt",
            content_type="application/vnd.ms-powerpoint",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_pptx_file(self):
        file = SimpleUploadedFile(
            "dummy.pptx",
            b"fake ppt",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_csv_file(self):
        file = SimpleUploadedFile(
            "dummy.csv",
            b"a,b,c\n1,2,3",
            content_type="text/csv",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_jpg_file(self):
        file = SimpleUploadedFile(
            "image.jpg",
            b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_jpeg_file(self):
        file = SimpleUploadedFile(
            "image.jpeg",
            b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_png_file(self):
        file = SimpleUploadedFile(
            "image.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_gif_file(self):
        file = SimpleUploadedFile(
            "image.gif",
            b"GIF89a",
            content_type="image/gif",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_zip_file(self):
        file = SimpleUploadedFile(
            "archive.zip",
            b"PK\x03\x04",
            content_type="application/zip",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_wrong_extension_with_pdf_mimetype(self):
        file = SimpleUploadedFile(
            "notpdf.txt",
            b"%PDF-1.4\nstuff",
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)

    def test_rejects_wrong_mimetype_with_pdf_extension(self):
        file = SimpleUploadedFile(
            "tricky.pdf",
            b"%PDF-1.4\nstuff",
            content_type="text/plain",
        )
        with self.assertRaises(ValidationError):
            validate_pdf_file(file)


class PdfSnifferTests(TestCase):
    """Tests for content integrity (actual PDF structure)"""

    def _temp_path(self, suffix):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.close()
        return f.name

    def test_valid_pdf_file(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Some content\n%%EOF")  

        sniffer = PdfSniffer()
        self.assertIsNone(sniffer.is_valid(file_path))

    def test_invalid_minimal_pdf_header(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF") 

        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_fake_pdf_with_txt_content(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "w") as f:
            f.write("Hello world") 

        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

    def test_corrupted_pdf_file(self):
        file_path = self._temp_path(".pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\n") 

        sniffer = PdfSniffer()
        with self.assertRaises(ValidationError):
            sniffer.is_valid(file_path)

# --- Positive Tests ---
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent
SAMPLE_PDF = BASE_DIR / "data" / "PDFsample.pdf"
def test_extract_fragments_from_valid_pdf():
    """Reader should extract fragments with coordinates from a real PDF"""
    reader = PdfReader()
    fragments = reader.extract(str(SAMPLE_PDF))

    assert isinstance(fragments, list)
    assert len(fragments) > 0

    first = fragments[0]
    assert isinstance(first, TextFragment)
    assert isinstance(first.page, int)
    assert isinstance(first.x, (int, float))
    assert isinstance(first.y, (int, float))
    assert isinstance(first.text, str)


def test_extract_contains_expected_keywords():
    """Fragments should contain at least one known header keyword like 'uraian'/'deskripsi' and 'volume' (even if on later pages)."""
    reader = PdfReader()
    fragments = reader.extract(str(SAMPLE_PDF))

    texts = [f.text.lower().replace("\xa0", " ") for f in fragments]

    description_headers = ["uraian", "uraian pekerjaan", "deskripsi", "pekerjaan"]

    found_desc = any(any(h in t for h in description_headers) for t in texts)
    found_vol = any("volume" in t for t in texts)

    assert found_desc, "No description-like header ('uraian', 'pekerjaan', etc.) found in PDF text"
    assert found_vol, "No 'volume' header found in PDF text"


# --- Negative Tests ---

def test_extract_from_nonexistent_file_raises():
    """Should raise FileNotFoundError if path is invalid"""
    reader = PdfReader()
    with pytest.raises(FileNotFoundError):
        reader.extract("nonexistent.pdf")


def test_extract_from_invalid_file_type_raises(tmp_path):
    """Should raise Exception if trying to read a non-PDF file"""
    fake_txt = tmp_path / "fake.txt"
    fake_txt.write_text("this is not a pdf")

    reader = PdfReader()
    with pytest.raises(Exception):
        reader.extract(str(fake_txt))


def test_extract_from_corrupted_pdf_raises(tmp_path):
    """Should raise Exception if PDF is corrupted"""
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4\nthis is junk data without EOF marker")

    reader = PdfReader()
    with pytest.raises(Exception):
        reader.extract(str(bad_pdf))

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
            TextFragment(page=1, x=i*10, y=50, text=f"Noise{i}") for i in range(50)
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
        # The implementation currently concatenates with single spaces
        self.assertEqual(merged, "Pekerjaan A (lanjutan)")

    def test_parse_single_page_two_rows(self):
        fragments = []
        # Header row at y=100
        fragments += self._headers_at(page=1, y=100)
        # Data rows below header; header_gap_px default=6.0, so y=110,130 are valid
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
        # Put a row at y = header_y + 4 < header_gap_px (6.0) → should be skipped
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
        # Page 1 header + row
        fragments += self._headers_at(page=1, y=90)
        fragments += self._row(page=1, y=110, no="1", uraian="P1", volume="1", satuan="m")

        # Page 2 header with different x layout + row
        fragments += self._headers_at(page=2, y=80, xs=[20, 180, 300, 420])
        fragments += self._row(page=2, y=100, no="2", uraian="P2", volume="2", satuan="kg", xs=[20, 180, 300, 420])

        rows, last_boundaries = self.parser.parse(fragments)

        # Should have both rows, ordered by page then y
        self.assertEqual([ (r.page, r.values["no"]) for r in rows ], [(1, "1"), (2, "2")])

        # last_boundaries should correspond to page 2 header positions (split around 20/180/300/420)
        self.assertIn("uraian", last_boundaries)
        ura_min, ura_max = last_boundaries["uraian"]
        self.assertLess(ura_min, 180)
        self.assertGreater(ura_max, 180)

    def test_parse_reuses_headers_without_new_header_row(self):
        fragments = []
        # Page 1 header + row
        fragments += self._headers_at(page=1, y=90)
        fragments += self._row(page=1, y=110, no="1", uraian="P1", volume="1", satuan="m")

        # Page 2 has no header row, only data near top of page
        fragments += [
            TextFragment(page=2, x=10, y=35, text="2"),
            TextFragment(page=2, x=120, y=35, text="P2"),
            TextFragment(page=2, x=260, y=35, text="2"),
            TextFragment(page=2, x=360, y=35, text="kg"),
        ]

        rows, _ = self.parser.parse(fragments)

        # Expect both rows to appear despite missing header on page 2
        numbers = [(r.page, r.values.get("no")) for r in rows]
        self.assertIn((1, "1"), numbers)
        self.assertIn((2, "2"), numbers)

    def test_parse_empty_or_no_headers(self):
        rows, bounds = self.parser.parse([])
        self.assertEqual(rows, [])
        self.assertEqual(bounds, {})


class PdfRowNormalizerTests(TestCase):

    def test_uppercase_header_keeps_letter_in_description(self):
        row = {
            "no": "",
            "uraian": "PEKERJAAN PERSIAPAN & SMKK",
            "satuan": "",
            "volume": "",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "PEKERJAAN PERSIAPAN & SMKK")

    def test_letter_with_punctuation_is_still_extracted(self):
        row = {
            "no": "",
            "uraian": "a.Peralatan P3K",
            "satuan": "set",
            "volume": "1",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "a")
        self.assertEqual(normalized["description"], "Peralatan P3K")

    def test_single_letter_word_not_split_as_roman(self):
        row = {
            "no": "",
            "uraian": "dan Reng",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "dan Reng")

    def test_numeric_fragment_without_unit_stays_in_description(self):
        row = {
            "no": "",
            "uraian": "23 Watt",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "23 Watt")

    def test_uppercase_word_not_split_as_roman(self):
        row = {
            "no": "",
            "uraian": "CNP 150.65.20.2,3",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "CNP 150.65.20.2,3")

    def test_word_number_prefix_merges_into_description(self):
        row = {
            "no": "di",
            "uraian": "uraikan dalam gambar",
            "satuan": "",
            "volume": "0",
            "price": "",
            "total_price": "",
            "analysis_code": "",
        }

        normalized = PdfRowNormalizer.normalize(row)

        self.assertEqual(normalized["number"], "")
        self.assertEqual(normalized["description"], "di uraikan dalam gambar")


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

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

class PdfParserViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_rab_converted_pdf_get(self):
        """
        RED: Pastikan GET ke /pdf_parser/rab_converted/ merender template.
        Akan gagal kalau view/urls/template belum dibuat.
        """
        url = reverse("pdf_parser:rab_converted_pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pdf_parser/rab_converted.html")

    def test_rab_converted_pdf_post_no_file(self):
        """
        RED: Pastikan POST tanpa file mengembalikan error 400.
        """
        url = reverse("pdf_parser:rab_converted_pdf")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_rab_converted_pdf_post_with_pdf(self):
        """
        RED: Pastikan POST dengan PDF valid mengembalikan JSON berisi rows.
        Awalnya akan gagal (500/empty), nanti GREEN setelah implementasi pipeline.
        """
        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",  
            content_type="application/pdf",
        )

        url = reverse("pdf_parser:rab_converted_pdf")
        response = self.client.post(url, {"pdf_file": dummy_pdf})
        self.assertEqual(response.status_code, 200)
        self.assertIn("rows", response.json())
