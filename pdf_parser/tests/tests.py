import tempfile
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
import os
import pytest
from pdf_parser.services.pdfreader import PdfReader,TextFragment

from pdf_parser.services.validators import validate_pdf_file
from pdf_parser.services.pdf_sniffer import PdfSniffer
from pdf_parser.services.header_mapper import PdfHeaderMapper, TextFragment
from pdf_parser.services.row_parser import PdfRowParser

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

class PdfHeaderMapperTests(TestCase):
    def setUp(self):
        self.mapper = PdfHeaderMapper()

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
        self.assertEqual(missing, [])

    def test_headers_out_of_order(self):
        fragments = [
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertTrue(set(["no","uraian","volume","satuan"]).issubset(mapping.keys()))
        self.assertEqual(missing, [])

    def test_duplicate_header_fragments(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text="No"),
            TextFragment(page=1, x=12, y=20, text="No"),  # duplicate
            TextFragment(page=1, x=100, y=20, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=200, y=20, text="Volume"),
            TextFragment(page=1, x=300, y=20, text="Satuan"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertEqual(missing, [])
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
        self.assertEqual(missing, [])

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
        self.assertEqual(missing, [])
        self.assertIn("uraian", mapping)

    # --- Negative / edge cases ---

    def test_empty_fragments(self):
        mapping, missing, _ = self.mapper.map_headers([])
        self.assertListEqual(missing, ["no","uraian","volume","satuan"])
        self.assertDictEqual(mapping, {})

    def test_fragments_with_empty_text(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text=""),
            TextFragment(page=1, x=100, y=20, text="  "),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(missing, ["no","uraian","volume","satuan"])
        self.assertDictEqual(mapping, {})

    def test_unrecognizable_headers(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text="Random1"),
            TextFragment(page=1, x=100, y=20, text="Random2"),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(missing, ["no","uraian","volume","satuan"])
        self.assertDictEqual(mapping, {})

    def test_fragments_with_none_or_whitespace(self):
        fragments = [
            TextFragment(page=1, x=10, y=20, text=None),
            TextFragment(page=1, x=100, y=20, text="   "),
        ]
        mapping, missing, _ = self.mapper.map_headers(fragments)
        self.assertListEqual(missing, ["no","uraian","volume","satuan"])
        self.assertDictEqual(mapping, {})

class PdfRowParserTests(TestCase):
    def setUp(self):
        self.parser = PdfRowParser(y_tolerance=0.8, x_merge_gap=40.0)

    def _hdr(self):
        return [
            TextFragment(page=1, x=10,  y=100.0, text="No"),
            TextFragment(page=1, x=120, y=100.0, text="Uraian"),
            TextFragment(page=1, x=260, y=100.0, text="Volume"),
            TextFragment(page=1, x=360, y=100.0, text="Satuan"),
        ]

    def test_simple_two_rows(self):
        frags = []
        frags += self._hdr()
        frags += [
            TextFragment(page=1, x=12,  y=120.1, text="1"),
            TextFragment(page=1, x=122, y=120.0, text="Pekerjaan"),
            TextFragment(page=1, x=190, y=120.0, text="A"),
            TextFragment(page=1, x=262, y=120.2, text="10"),
            TextFragment(page=1, x=362, y=120.1, text="m2"),
        ]
        frags += [
            TextFragment(page=1, x=12,  y=135.0, text="2"),
            TextFragment(page=1, x=122, y=135.1, text="Pekerjaan B"),
            TextFragment(page=1, x=262, y=135.1, text="5"),
            TextFragment(page=1, x=362, y=135.1, text="m1"),
        ]

        rows, bounds = self.parser.parse(frags)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].values["no"], "1")
        self.assertEqual(rows[0].values["uraian"], "Pekerjaan A")
        self.assertEqual(rows[0].values["volume"], "10")
        self.assertEqual(rows[0].values["satuan"], "m2")

        self.assertEqual(rows[1].values["no"], "2")
        self.assertEqual(rows[1].values["uraian"], "Pekerjaan B")
        self.assertEqual(rows[1].values["volume"], "5")
        self.assertEqual(rows[1].values["satuan"], "m1")

        for key in ["no", "uraian", "volume", "satuan"]:
            self.assertIn(key, bounds)

    def test_fragments_split_within_cell_are_merged(self):
        frags = []
        frags += self._hdr()
        frags += [
            TextFragment(page=1, x=12,  y=120.0, text="1"),
            TextFragment(page=1, x=122, y=120.0, text="Pekerjaan"),
            TextFragment(page=1, x=190, y=120.0, text="C"),     
            TextFragment(page=1, x=200, y=120.0, text="(Lanjutan)"),
            TextFragment(page=1, x=262, y=120.0, text="12"),
            TextFragment(page=1, x=362, y=120.0, text="unit"),
        ]
        rows, _ = self.parser.parse(frags)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].values["uraian"], "Pekerjaan C (Lanjutan)")

    def test_multi_page_with_repeated_headers(self):
        frags = [
            TextFragment(page=1, x=10,  y=100.0, text="No"),
            TextFragment(page=1, x=120, y=100.0, text="Uraian Pekerjaan"),
            TextFragment(page=1, x=260, y=100.0, text="Volume"),
            TextFragment(page=1, x=360, y=100.0, text="Satuan"),
            TextFragment(page=1, x=12,  y=120.0, text="1"),
            TextFragment(page=1, x=122, y=120.0, text="Row1"),
            TextFragment(page=1, x=262, y=120.0, text="3"),
            TextFragment(page=1, x=362, y=120.0, text="m"),
        ]
        frags += [
            TextFragment(page=2, x=10,  y=95.0,  text="No"),
            TextFragment(page=2, x=120, y=95.0,  text="Uraian"),
            TextFragment(page=2, x=260, y=95.0,  text="Volume"),
            TextFragment(page=2, x=360, y=95.0,  text="Satuan"),
            TextFragment(page=2, x=12,  y=115.0, text="2"),
            TextFragment(page=2, x=122, y=115.0, text="Row2"),
            TextFragment(page=2, x=262, y=115.0, text="7"),
            TextFragment(page=2, x=362, y=115.0, text="m"),
        ]
        rows, _ = self.parser.parse(frags)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].page, 1)
        self.assertEqual(rows[1].page, 2)
        self.assertEqual(rows[1].values["no"], "2")
        self.assertEqual(rows[1].values["uraian"], "Row2")

    def test_ignores_noise_before_header_and_very_close_to_header(self):
        noise = [
            TextFragment(page=1, x=50, y=60.0, text="Some Title"),
            TextFragment(page=1, x=50, y=80.0, text="Misc"),
        ]
        hdr = self._hdr()  
        near_header = [
            TextFragment(page=1, x=12,  y=104.0, text="SHOULD_NOT_PARSE"),
        ]
        valid_row = [
            TextFragment(page=1, x=12,  y=112.5, text="1"),
            TextFragment(page=1, x=122, y=112.4, text="OK"),
            TextFragment(page=1, x=262, y=112.6, text="9"),
            TextFragment(page=1, x=362, y=112.7, text="m"),
        ]
        rows, _ = self.parser.parse(noise + hdr + near_header + valid_row)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].values["uraian"], "OK")