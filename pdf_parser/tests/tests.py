import json
import tempfile
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from pdf_parser.services.pdfreader import PdfReader,TextFragment
from unittest.mock import patch

from pdf_parser.services.validators import validate_pdf_file
from pdf_parser.services.pdf_sniffer import PdfSniffer
from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment
from pdf_parser.services.row_parser import PdfRowParser, ParsedRow
from pdf_parser.services.normalizer import PdfRowNormalizer
from pdf_parser.services.pipeline import merge_broken_rows
from pdf_parser.services.header_mapper import TextFragment

from django.test import TestCase, RequestFactory
import os

from pdf_parser.views import parse_pdf_view, NO_FILE_UPLOADED_MSG



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

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_rab_converted_pdf_post_converts_decimals(self, mock_parse):
        # parse returns Decimal values that should be converted to float in JSON
        mock_parse.return_value = [
            {"description": "Item", "volume": Decimal("1.5"), "price": Decimal("100.00")}
        ]

        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:rab_converted_pdf")
        response = self.client.post(url, {"pdf_file": dummy_pdf})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rows", data)
        self.assertIsInstance(data["rows"][0]["volume"], float)
        self.assertEqual(data["rows"][0]["volume"], 1.5)
        self.assertIsInstance(data["rows"][0]["price"], float)
        self.assertEqual(data["rows"][0]["price"], 100.0)

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_rab_converted_pdf_post_pipeline_error_returns_500(self, mock_parse):
        mock_parse.side_effect = Exception("pipeline failure")

        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:rab_converted_pdf")
        response = self.client.post(url, {"pdf_file": dummy_pdf})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("error", data)
        # view returns rows: [] on exception
        self.assertIn("rows", data)
        self.assertEqual(data["rows"], [])

    def test_parse_pdf_view_post_no_file_returns_400(self):
        url = reverse("pdf_parser:parse_pdf_view")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_parse_pdf_view_post_with_decimal_rows(self, mock_parse):
        mock_parse.return_value = [{"volume": Decimal("2.25"), "description": "X"}]

        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:parse_pdf_view")
        response = self.client.post(url, {"file": dummy_pdf})
        self.assertEqual(response.status_code, 200)
        # response.json() should return {"rows": [...]}
        data = response.json()
        self.assertIn("rows", data)
        self.assertIsInstance(data["rows"][0]["volume"], float)
        self.assertEqual(data["rows"][0]["volume"], 2.25)

    def test_upload_pdf_get_renders_template(self):
        url = reverse("pdf_parser:upload_pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Template name may be resolved under app templates; at minimum ensure OK
        self.assertTrue(response.templates)

    def test_preview_pdf_post_no_file_returns_400(self):
        url = reverse("pdf_parser:preview_pdf")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_preview_pdf_post_with_file_returns_mock_rows(self):
        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:preview_pdf")
        response = self.client.post(url, {"pdf_file": dummy_pdf})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rows", data)
        self.assertIsInstance(data["rows"], list)
        self.assertGreaterEqual(len(data["rows"]), 1)

    def test_preview_get_not_allowed(self):
        url = reverse("preview-pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_preview_post_no_file_returns_400(self):
        url = reverse("preview-pdf")
        response = self.client.post(url, {}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertIn("error", data)
        self.assertEqual(data["error"], NO_FILE_UPLOADED_MSG)

    def test_preview_post_with_pdf_returns_rows(self):
        url = reverse("preview-pdf")
        pdf_file = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF\n",
            content_type="application/pdf",
        )
        response = self.client.post(url, {"pdf_file": pdf_file})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertIn("rows", data)
        self.assertIsInstance(data["rows"], list)
        self.assertEqual(len(data["rows"]), 2)
        expected_keys = {"description", "code", "volume", "unit", "price", "total_price"}
        for row in data["rows"]:
            self.assertTrue(expected_keys.issubset(set(row.keys())))

    def test_parse_pdf_view_get_not_allowed(self):
        url = reverse("pdf_parser:parse_pdf_view")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_upload_pdf_post_not_allowed(self):
        url = reverse("pdf_parser:upload_pdf")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 405)

    def test_rab_converted_pdf_post_pipeline_error_with_unlink_oserror(self):
        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:rab_converted_pdf")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=Exception("boom")), \
             patch("os.path.exists", return_value=True), \
             patch("os.unlink", side_effect=OSError("cannot delete")):
            response = self.client.post(url, {"pdf_file": dummy_pdf})
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("rows", data)
        self.assertEqual(data["rows"], [])

    def test_parse_pdf_view_post_pipeline_error_and_unlink_oserror(self):
        dummy_pdf = SimpleUploadedFile(
            "dummy.pdf",
            b"%PDF-1.4\n%Fake PDF",
            content_type="application/pdf",
        )
        url = reverse("pdf_parser:parse_pdf_view")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=Exception("boom")), \
             patch("os.path.exists", return_value=True), \
             patch("os.unlink", side_effect=OSError("cannot delete")):
            response = self.client.post(url, {"file": dummy_pdf})
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("error", data)

    def test_preview_get_not_allowed_using_app_namespace(self):
        # ensure the view's NOT_ALLOWED branch is exercised using the app URL name
        url = reverse("pdf_parser:preview_pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_rab_converted_pdf_method_not_allowed(self):
        url = reverse("pdf_parser:rab_converted_pdf")
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 405)

    def test_parse_pdf_view_get_not_allowed(self):
        url = reverse("pdf_parser:parse_pdf_view")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(resp.json().get("error"), "Only POST allowed")

    def test_parse_pdf_view_post_no_file(self):
        url = reverse("pdf_parser:parse_pdf_view")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("error"), NO_FILE_UPLOADED_MSG)

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_parse_pdf_view_post_success_unlinks_tmpfile(self, mock_parse):
        mock_parse.return_value = [{"volume": Decimal("1.5")}]
        pdf = SimpleUploadedFile("f.pdf", b"%PDF-1.4\nfake", content_type="application/pdf")
        url = reverse("pdf_parser:parse_pdf_view")
        with patch("os.path.exists", return_value=True), patch("os.unlink") as mock_unlink:
            resp = self.client.post(url, {"file": pdf})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("rows", data)
            # Decimal should be converted to float
            self.assertEqual(data["rows"][0]["volume"], 1.5)
            mock_unlink.assert_called_once()

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_parse_pdf_view_post_exception_and_unlink_oserror(self, mock_parse):
        mock_parse.side_effect = Exception("boom")
        pdf = SimpleUploadedFile("f.pdf", b"%PDF-1.4\nfake", content_type="application/pdf")
        url = reverse("pdf_parser:parse_pdf_view")
        with patch("os.path.exists", return_value=True), patch("os.unlink", side_effect=OSError("no del")) as mock_unlink:
            resp = self.client.post(url, {"file": pdf})
            self.assertEqual(resp.status_code, 500)
            data = resp.json()
            self.assertIn("error", data)
            mock_unlink.assert_called_once()

    def test_get_not_allowed_returns_405_and_message(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(resp.json().get("error"), "Only POST allowed")

    def test_post_no_file_returns_400(self):
        resp = self.client.post(self.url, {})  # no 'file' key
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("error"), NO_FILE_UPLOADED_MSG)

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_post_success_converts_decimals_and_unlinks_tmpfile(self, mock_parse):
        # parse returns Decimal values -> should be converted to float
        mock_parse.return_value = [{"volume": Decimal("1.23"), "desc": "X"}]
        pdf = SimpleUploadedFile("f.pdf", b"%PDF-1.4\nfake", content_type="application/pdf")

        with patch("os.path.exists", return_value=True) as mock_exists, \
             patch("os.unlink") as mock_unlink:
            resp = self.client.post(self.url, {"file": pdf})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("rows", data)
            self.assertIsInstance(data["rows"], list)
            self.assertEqual(data["rows"][0]["volume"], 1.23)  # Decimal -> float
            mock_exists.assert_called()   # tmp existence checked
            mock_unlink.assert_called_once()  # tmp file cleanup attempted

    @patch("pdf_parser.views.parse_pdf_to_dtos")
    def test_post_pipeline_exception_returns_500_and_handles_unlink_oserror(self, mock_parse):
        mock_parse.side_effect = Exception("pipeline-fail")
        pdf = SimpleUploadedFile("f.pdf", b"%PDF-1.4\nfake", content_type="application/pdf")

        # simulate os.unlink raising OSError (should be caught and ignored by view)
        with patch("os.path.exists", return_value=True) as mock_exists, \
             patch("os.unlink", side_effect=OSError("cant remove")) as mock_unlink:
            resp = self.client.post(self.url, {"file": pdf})
            self.assertEqual(resp.status_code, 500)
            data = resp.json()
            self.assertIn("error", data)
            mock_exists.assert_called()
            mock_unlink.assert_called_once()

class ParsePdfViewTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_get_not_allowed(self):
        req = self.rf.get("/parse-pdf")
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 405)
        data = json.loads(resp.content)
        self.assertIn("Only POST", data.get("error", ""))

    def test_post_no_file(self):
        req = self.rf.post("/parse-pdf", {})  # no file provided
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertEqual(data.get("error"), NO_FILE_UPLOADED_MSG)

    def test_post_success_converts_decimals_and_cleans_tmp(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse(path):
            # during parse the temp file must exist
            seen["path"] = path
            assert os.path.exists(path), "temp file should exist while parsing"
            return [{"val": Decimal("12.34")}]

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        # Decimal should be converted to float
        self.assertIn("rows", data)
        self.assertEqual(data["rows"][0]["val"], 12.34)
        # temp file should have been removed by the view
        assert "path" in seen
        self.assertFalse(os.path.exists(seen["path"]))

    def test_post_parse_exception_returns_500_and_cleans_tmp(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse_raise(path):
            seen["path"] = path
            assert os.path.exists(path), "temp file should exist while parsing"
            raise RuntimeError("boom")

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse_raise):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertIn("boom", data.get("error", ""))
        assert "path" in seen
        self.assertFalse(os.path.exists(seen["path"]))

    def test_post_success_regular(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse(path):
            seen["path"] = path
            assert os.path.exists(path)
            return [{"val": Decimal("12.34")}]

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("rows", data)
        self.assertEqual(data["rows"][0]["val"], 12.34)
        # cleanup temp file created by view
        if "path" in seen and os.path.exists(seen["path"]):
            os.unlink(seen["path"])

    def test_post_unlink_raises_oserror_on_success(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse(path):
            seen["path"] = path
            assert os.path.exists(path)
            return [{"val": Decimal("1.0")}]

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("unlink failed")) as mock_unlink:
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["rows"][0]["val"], 1.0)
        self.assertTrue(mock_unlink.called)
        # temp file likely still exists because unlink failed; remove it now
        if "path" in seen and os.path.exists(seen["path"]):
            os.unlink(seen["path"])

    def test_post_parse_exception_regular(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse_raise(path):
            seen["path"] = path
            assert os.path.exists(path)
            raise RuntimeError("boom")

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse_raise):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertIn("boom", data.get("error", ""))
        if "path" in seen and os.path.exists(seen["path"]):
            os.unlink(seen["path"])

    def test_post_parse_exception_unlink_raises_oserror(self):
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        seen = {}

        def fake_parse_raise(path):
            seen["path"] = path
            assert os.path.exists(path)
            raise RuntimeError("boom2")

        req = self.rf.post("/parse-pdf", {"file": uploaded}, content_type="multipart/form-data")
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse_raise), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("unlink failed")) as mock_unlink:
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertIn("boom2", data.get("error", ""))
        self.assertTrue(mock_unlink.called)
        if "path" in seen and os.path.exists(seen["path"]):
            os.unlink(seen["path"])

    def test_get_not_allowed_and_no_file(self):
        # GET not allowed
        req = self.rf.get("/parse-pdf")
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 405)
        data = json.loads(resp.content)
        self.assertIn("Only POST", data.get("error", ""))

        # POST with no file
        req = self.rf.post("/parse-pdf", {})
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertEqual(data.get("error"), NO_FILE_UPLOADED_MSG)

    def test_get_not_allowed(self):
        from pdf_parser.views import parse_pdf_view
        req = self.factory.get("/")
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 405)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Only POST allowed")

    def test_post_no_file_returns_400(self):
        from pdf_parser.views import parse_pdf_view, NO_FILE_UPLOADED_MSG
        req = self.factory.post("/")
        # No file attached
        resp = parse_pdf_view(req)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], NO_FILE_UPLOADED_MSG)

    def test_post_success_converts_decimals_and_cleans_tmp(self):
        from pdf_parser.views import parse_pdf_view
        from django.core.files.uploadedfile import SimpleUploadedFile
        from decimal import Decimal
        from unittest.mock import patch

        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF", content_type="application/pdf")
        req = self.factory.post("/")
        req._files = {"file": uploaded}

        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("os.path.exists") as mock_exists, \
             patch("os.unlink") as mock_unlink:
            mock_parse.return_value = [{"description": "X", "volume": Decimal("2.5")}]
            mock_exists.return_value = True

            resp = parse_pdf_view(req)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("rows", data)
            self.assertIsInstance(data["rows"], list)
            self.assertEqual(data["rows"][0]["volume"], 2.5)
            mock_unlink.assert_called()

    def test_post_parse_exception_returns_500_and_cleans_tmp(self):
        from pdf_parser.views import parse_pdf_view
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF", content_type="application/pdf")
        req = self.factory.post("/")
        req._files = {"file": uploaded}

        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("os.path.exists") as mock_exists, \
             patch("os.unlink") as mock_unlink:
            mock_parse.side_effect = ValueError("parse failed")
            mock_exists.return_value = True

            resp = parse_pdf_view(req)
            self.assertEqual(resp.status_code, 500)
            data = resp.json()
            self.assertIn("error", data)
            self.assertIn("parse failed", data["error"])
            mock_unlink.assert_called()

    def test_post_unlink_raises_oserror_on_success(self):
        from pdf_parser.views import parse_pdf_view
        from django.core.files.uploadedfile import SimpleUploadedFile
        from decimal import Decimal
        from unittest.mock import patch

        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF", content_type="application/pdf")
        req = self.factory.post("/")
        req._files = {"file": uploaded}

        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("os.path.exists") as mock_exists, \
             patch("os.unlink") as mock_unlink:
            mock_parse.return_value = [{"description": "Y", "volume": Decimal("7.0")}]
            mock_exists.return_value = True
            mock_unlink.side_effect = OSError("unlink failed")

            # Should not raise; view swallows OSError from unlink
            resp = parse_pdf_view(req)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["rows"][0]["volume"], 7.0)
            mock_unlink.assert_called()

    def test_post_unlink_raises_oserror_on_exception(self):
        from pdf_parser.views import parse_pdf_view
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF", content_type="application/pdf")
        req = self.factory.post("/")
        req._files = {"file": uploaded}

        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("os.path.exists") as mock_exists, \
             patch("os.unlink") as mock_unlink:
            mock_parse.side_effect = RuntimeError("boom")
            mock_exists.return_value = True
            mock_unlink.side_effect = OSError("unlink failed")

            resp = parse_pdf_view(req)
            self.assertEqual(resp.status_code, 500)
            data = resp.json()
            self.assertIn("error", data)
            self.assertIn("boom", data["error"])
            mock_unlink.assert_called()

    def _make_req_with_file(self, file_obj):
        req = self.rf.post("/parse-pdf", {}, content_type="multipart/form-data")
        # attach file object directly to request to trigger the 'for chunk in file.chunks()' loop
        req._files = {"file": file_obj}
        return req

    def test_try_block_writes_chunks_and_cleans_tempfile(self):
        # Fake uploaded file that yields multiple chunks
        class FakeUploaded:
            def __init__(self, parts):
                self._parts = parts

            def chunks(self):
                for p in self._parts:
                    yield p

        uploaded = FakeUploaded([b"%PDF-1.4\n", b"body", b"\n%%EOF"])
        seen = {}

        def fake_parse(path):
            # ensure temp file exists while parser is called and capture path
            seen["path"] = path
            assert os.path.exists(path)
            return [{"v": Decimal("9.9")}]

        req = self._make_req_with_file(uploaded)
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("rows", data)
        # Decimal converted to float
        self.assertEqual(data["rows"][0]["v"], 9.9)
        # temp file was removed in finally
        self.assertIn("path", seen)
        self.assertFalse(os.path.exists(seen["path"]))

    def test_except_path_returns_500_and_still_cleans_tmpfile(self):
        class FakeUploaded:
            def chunks(self):
                yield b"%PDF-1.4\n"
        uploaded = FakeUploaded()
        seen = {}

        def fake_parse_fail(path):
            seen["path"] = path
            assert os.path.exists(path)
            raise RuntimeError("parse-fail")

        req = self._make_req_with_file(uploaded)
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=fake_parse_fail):
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertIn("parse-fail", data.get("error", ""))
        # temp file cleaned even on exception
        self.assertIn("path", seen)
        self.assertFalse(os.path.exists(seen["path"]))

    def test_finally_handles_tmp_path_none_gracefully(self):
        # Simulate NamedTemporaryFile failing so tmp_path remains None
        uploaded = SimpleUploadedFile("f.pdf", b"%PDF-1.4\n", content_type="application/pdf")
        req = self._make_req_with_file(uploaded)

        # Make NamedTemporaryFile raise OSError to simulate failure before tmp_path assignment
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("no tmp")), \
             patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            # parse should not be called because tmp creation failed, but view should handle it
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertIn("error", data)

class ParsePdfViewComprehensiveTests(TestCase):
    """Comprehensive test coverage for parse_pdf_view lines 77-102"""
    
    def setUp(self):
        self.rf = RequestFactory()
        self.url = "/parse-pdf"

    # ===== POSITIVE TESTS =====
    
    def test_post_success_with_simple_data(self):
        """Test successful POST with simple parsed data"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [{"description": "Item", "volume": 1}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertIn("rows", data)
            self.assertEqual(len(data["rows"]), 1)
            self.assertEqual(data["rows"][0]["description"], "Item")

    def test_post_success_converts_decimals_to_floats(self):
        """Test that Decimal values are properly converted to float"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [
                {"volume": Decimal("12.345"), "price": Decimal("100.50")},
                {"volume": Decimal("5.0"), "price": Decimal("200")}
            ]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertEqual(data["rows"][0]["volume"], 12.345)
            self.assertEqual(data["rows"][0]["price"], 100.50)
            self.assertIsInstance(data["rows"][0]["volume"], float)
            self.assertIsInstance(data["rows"][0]["price"], float)

    def test_post_success_with_nested_decimals(self):
        """Test conversion of nested Decimal objects"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [
                {
                    "items": [
                        {"amount": Decimal("1.5")},
                        {"amount": Decimal("2.7")}
                    ],
                    "total": Decimal("4.2")
                }
            ]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertEqual(data["rows"][0]["items"][0]["amount"], 1.5)
            self.assertEqual(data["rows"][0]["total"], 4.2)

    def test_post_success_with_empty_rows(self):
        """Test successful POST when parser returns empty list"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = []
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertIn("rows", data)
            self.assertEqual(data["rows"], [])

    def test_post_success_temp_file_cleanup(self):
        """Test that temp file is created and cleaned up properly"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        temp_path_holder = {}
        
        def capture_path(path):
            temp_path_holder["path"] = path
            self.assertTrue(os.path.exists(path), "Temp file should exist during parse")
            return [{"item": "test"}]
        
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=capture_path):
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            # Verify temp file was cleaned up
            self.assertIn("path", temp_path_holder)
            self.assertFalse(os.path.exists(temp_path_holder["path"]), 
                           "Temp file should be deleted after processing")

    def test_post_success_with_large_file_chunks(self):
        """Test handling of large file uploaded in chunks"""
        # Simulate large file
        large_content = b"%PDF-1.4\n" + b"x" * 10000
        uploaded = SimpleUploadedFile("large.pdf", large_content, content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [{"item": "large"}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            # Verify parser was called
            mock_parse.assert_called_once()
            # Verify temp file path passed to parser
            call_args = mock_parse.call_args[0]
            self.assertTrue(call_args[0].endswith(".pdf"))

    # ===== NEGATIVE TESTS =====

    def test_post_parse_raises_value_error(self):
        """Test handling of ValueError during parsing"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.side_effect = ValueError("Invalid PDF structure")
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 500)
            data = json.loads(resp.content)
            self.assertIn("error", data)
            self.assertIn("Invalid PDF structure", data["error"])

    def test_post_parse_raises_runtime_error(self):
        """Test handling of RuntimeError during parsing"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.side_effect = RuntimeError("Parser crashed")
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 500)
            data = json.loads(resp.content)
            self.assertIn("Parser crashed", data["error"])

    def test_post_parse_raises_generic_exception(self):
        """Test handling of generic Exception during parsing"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.side_effect = Exception("Unexpected error")
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 500)
            data = json.loads(resp.content)
            self.assertIn("Unexpected error", data["error"])

    def test_post_parse_exception_still_cleans_temp_file(self):
        """Test that temp file is cleaned up even when parsing raises exception"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        temp_path_holder = {}
        
        def raise_and_capture(path):
            temp_path_holder["path"] = path
            self.assertTrue(os.path.exists(path))
            raise RuntimeError("Parse failed")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=raise_and_capture):
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 500)
            # Verify temp file was still cleaned up
            self.assertIn("path", temp_path_holder)
            self.assertFalse(os.path.exists(temp_path_holder["path"]))

    # ===== EDGE CASES =====

    def test_post_unlink_fails_on_success_path(self):
        """Test that OSError during cleanup on success path is silently caught"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("pdf_parser.views.os.path.exists", return_value=True), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("Permission denied")):
            
            mock_parse.return_value = [{"item": "test"}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            # Should still return 200 despite unlink failure
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertIn("rows", data)

    def test_post_unlink_fails_on_exception_path(self):
        """Test that OSError during cleanup on exception path is silently caught"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("pdf_parser.views.os.path.exists", return_value=True), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("File locked")):
            
            mock_parse.side_effect = RuntimeError("Parse error")
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            # Should return 500 with parse error, not unlink error
            self.assertEqual(resp.status_code, 500)
            data = json.loads(resp.content)
            self.assertIn("Parse error", data["error"])
            self.assertNotIn("File locked", data["error"])

    def test_post_temp_file_not_exists_after_parse(self):
        """Test when temp file doesn't exist during cleanup (edge case)"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse, \
             patch("pdf_parser.views.os.path.exists", return_value=False), \
             patch("pdf_parser.views.os.unlink") as mock_unlink:
            
            mock_parse.return_value = [{"item": "test"}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            # unlink should NOT be called if file doesn't exist
            mock_unlink.assert_not_called()

    def test_post_tmp_path_none_in_finally(self):
        """Test edge case where tmp_path stays None (shouldn't happen but covered)"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        # This simulates tempfile creation failing before assignment
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("No space")):
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 500)
            data = json.loads(resp.content)
            self.assertIn("error", data)

    def test_post_with_special_characters_in_filename(self):
        """Test handling of files with special characters in name"""
        uploaded = SimpleUploadedFile(
            "tëst ფაილი 测试.pdf", 
            b"%PDF-1.4 content", 
            content_type="application/pdf"
        )
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [{"item": "special"}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)

    def test_post_multiple_chunks_written_correctly(self):
        """Test that multiple file chunks are written correctly to temp file"""
        # Create a file that will be chunked
        content = b"%PDF-1.4\n" + b"a" * 5000
        uploaded = SimpleUploadedFile("test.pdf", content, content_type="application/pdf")
        
        captured_content = []
        
        def capture_and_parse(path):
            with open(path, "rb") as f:
                captured_content.append(f.read())
            return [{"item": "chunked"}]
        
        with patch("pdf_parser.views.parse_pdf_to_dtos", side_effect=capture_and_parse):
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            # Verify all content was written
            self.assertEqual(len(captured_content), 1)
            self.assertEqual(captured_content[0], content)

    def test_post_returns_json_with_safe_false(self):
        """Test that JsonResponse is called with safe=False for list response"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            # Return a list
            mock_parse.return_value = [{"a": 1}, {"b": 2}]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertIsInstance(data["rows"], list)
            self.assertEqual(len(data["rows"]), 2)

    def test_post_complex_decimal_conversion(self):
        """Test conversion of complex nested structures with Decimals"""
        uploaded = SimpleUploadedFile("test.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        
        with patch("pdf_parser.views.parse_pdf_to_dtos") as mock_parse:
            mock_parse.return_value = [
                {
                    "level1": {
                        "level2": [
                            {"value": Decimal("1.111")},
                            {"value": Decimal("2.222")}
                        ]
                    },
                    "direct": Decimal("3.333")
                }
            ]
            
            req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")
            resp = parse_pdf_view(req)
            
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertEqual(data["rows"][0]["level1"]["level2"][0]["value"], 1.111)
            self.assertEqual(data["rows"][0]["direct"], 3.333)

    def test_parse_pdf_view_unlink_raises_is_silently_handled(self):
        """Ensure the except OSError: pass branch in parse_pdf_view.finally is executed."""
        uploaded = SimpleUploadedFile("f.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        req = self.rf.post(self.url, {"file": uploaded}, content_type="multipart/form-data")

        with patch("pdf_parser.views.parse_pdf_to_dtos", return_value=[{"ok": True}]), \
             patch("pdf_parser.views.os.path.exists", return_value=True), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("cannot delete")) as mock_unlink:
            resp = parse_pdf_view(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("rows", data)
        mock_unlink.assert_called_once()

    def test_parse_pdf_view_finally_catches_unlink_oserror(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch
        uploaded = SimpleUploadedFile("f.pdf", b"%PDF-1.4\nfake", content_type="application/pdf")

        # RequestFactory doesn't automatically populate request.FILES reliably for multipart here,
        # so attach the file directly to request._files to ensure the view writes chunks.
        req = self.rf.post("/parse-pdf", content_type="multipart/form-data")
        req._files = {"file": uploaded}

        with patch("pdf_parser.views.parse_pdf_to_dtos", return_value=[{"ok": True}]), \
             patch("pdf_parser.views.os.path.exists", return_value=True), \
             patch("pdf_parser.views.os.unlink", side_effect=OSError("cannot delete")) as mock_unlink:
            resp = parse_pdf_view(req)

        # view should return success and swallow the OSError from unlink (executes except OSError: pass)
        self.assertEqual(resp.status_code, 200)
        mock_unlink.assert_called_once()