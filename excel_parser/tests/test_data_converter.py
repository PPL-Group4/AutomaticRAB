from django.test import TestCase
from decimal import Decimal
from datetime import date
from excel_parser.services.data_converter import DataConverter


class DataConverterTests(TestCase):
    def setUp(self):
        self.conv = DataConverter()

    def test_to_decimal_formats(self):
        self.assertEqual(self.conv.to_decimal("1234.56"), Decimal("1234.56"))
        self.assertEqual(self.conv.to_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(self.conv.to_decimal("1,234.56"), Decimal("1234.56"))
        self.assertEqual(self.conv.to_decimal("1.000"), Decimal("1000"))
        self.assertEqual(self.conv.to_decimal("5.000"), Decimal("5000"))
        self.assertEqual(self.conv.to_decimal("Rp 5.000"), Decimal("5000"))
        self.assertEqual(self.conv.to_decimal("1.234.567,89"), Decimal("1234567.89"))
        self.assertEqual(self.conv.to_decimal("1,234,567.89"), Decimal("1234567.89"))
        self.assertEqual(self.conv.to_decimal("1.23E+5"), Decimal("123000"))
        self.assertIsNone(self.conv.to_decimal("abc"))
        self.assertIsNone(self.conv.to_decimal(""))
        self.assertIsNone(self.conv.to_decimal(None))

    def test_to_decimal_multiple_periods_and_commas(self):
        self.assertEqual(self.conv.to_decimal("12.34,56"), Decimal("1234.56"))
        self.assertEqual(self.conv.to_decimal("1.2.3,4"), Decimal("123.4"))

    def test_to_percentage_valid_and_invalid(self):
        self.assertEqual(self.conv.to_percentage("50%"), Decimal("0.5"))
        self.assertEqual(self.conv.to_percentage("0%"), Decimal("0"))
        self.assertIsNone(self.conv.to_percentage("invalid"))
        self.assertIsNone(self.conv.to_percentage(""))
        self.assertIsNone(self.conv.to_percentage(None))

    def test_to_boolean_true_false_none(self):
        self.assertTrue(self.conv.to_boolean("TRUE"))
        self.assertTrue(self.conv.to_boolean("true"))
        self.assertFalse(self.conv.to_boolean("FALSE"))
        self.assertFalse(self.conv.to_boolean("false"))
        self.assertIsNone(self.conv.to_boolean("maybe"))
        self.assertIsNone(self.conv.to_boolean(None))

    def test_to_date_formats_and_invalid(self):
        self.assertEqual(self.conv.to_date("2024-12-31"), date(2024, 12, 31))
        self.assertEqual(self.conv.to_date("31/12/2024"), date(2024, 12, 31))
        self.assertIsNone(self.conv.to_date("31-12-2024"))
        self.assertIsNone(self.conv.to_date(None))
        self.assertIsNone(self.conv.to_date("invalid"))
