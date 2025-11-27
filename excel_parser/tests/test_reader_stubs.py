# excel_parser/tests/test_reader_stubs.py
from django.test import TestCase
from decimal import Decimal
from excel_parser.services.reader import _parse_rows, ParsedRow

class StubReader:
    """A simple stub that simulates iter_rows output."""
    def iter_rows(self, file=None):
        return [
            ["No", "Description", "Volume", "Satuan", "Analysis Code", "Price", "Total"],
            ["1", "Batu Kali", "10", "m3", "A.01", "50000", "500000"],
            ["2", "Pasir Urug", "5", "m3", "A.02", "75000", "375000"],
        ]

class ReaderStubTests(TestCase):
    def test_parse_rows_with_stub_input(self):
        # Arrange
        stub_rows = StubReader().iter_rows()
        colmap = {
            "number": 0,
            "description": 1,
            "volume": 2,
            "unit": 3,
            "analysis_code": 4,
            "price": 5,
            "total_price": 6,
            "_header_row": 0,
        }

        # Act
        parsed = _parse_rows(stub_rows, colmap)

        # Assert
        self.assertEqual(len(parsed), 2)

        first = parsed[0]
        self.assertEqual(first.number, "1")
        self.assertEqual(first.description, "Batu Kali")
        self.assertEqual(first.volume, Decimal("10"))
        self.assertEqual(first.unit, "m3")
        self.assertEqual(first.analysis_code, "A.01")
        self.assertEqual(first.price, Decimal("50000"))
