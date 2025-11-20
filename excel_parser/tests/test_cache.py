from django.test import TestCase
from excel_parser.services.cache import (
    cache_match_description,
    cache_parse_decimal,
)
from excel_parser.services.job_matcher import match_description
from excel_parser.services.reader import parse_decimal
from decimal import Decimal


class TestCacheFunctions(TestCase):

    def test_cache_parse_decimal_positive(self):
        """parse_decimal should correctly convert a normal numeric string."""
        result = cache_parse_decimal("123.45")
        self.assertEqual(result, Decimal("123.45"))

    def test_cache_parse_decimal_negative(self):
        """parse_decimal should return 0 for invalid values."""
        result = cache_parse_decimal("abc")
        self.assertEqual(result, Decimal("0"))

    def test_cache_parse_decimal_caching(self):
        """Calling cache_parse_decimal twice should hit the cache the 2nd time."""
        # Clear the cache first
        cache_parse_decimal.cache_clear()

        # First call is a real computation
        result1 = cache_parse_decimal("1000")

        # Second call should return cached result
        result2 = cache_parse_decimal("1000")

        self.assertIs(result1, result2)  # same object = cached

    def test_cache_match_description_positive(self):
        """Verify that match_description returns a dict when valid."""
        result = cache_match_description("gali tanah")
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    def test_cache_match_description_caching(self):
        """Second call should return cached output."""
        cache_match_description.cache_clear()

        first = cache_match_description("pasang batu")
        second = cache_match_description("pasang batu")

        self.assertIs(first, second)  # same object → cached

    def test_cache_match_description_invalid(self):
        """Invalid descriptions should still return a dict, not crash."""
        result = cache_match_description("")
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
