from decimal import Decimal

from django.test import SimpleTestCase


class AhspPriceRetrievalTests(SimpleTestCase):
    def setUp(self) -> None:
        # Import inside setUp to reflect TDD style and avoid import errors before impl
        from automatic_price_matching.price_retrieval import (
            AhspPriceRetriever,
            MockAhspSource,
        )

        # Create a mock AHSP source with canonical codes and prices
        self.source = MockAhspSource(
            {
                "AT.01.001": Decimal("250000.00"),
                "BT.02.010": Decimal("12500"),
            }
        )
        self.retriever = AhspPriceRetriever(self.source)

    def test_exact_code_returns_price(self) -> None:
        price = self.retriever.get_price_by_job_code("AT.01.001")
        self.assertEqual(price, Decimal("250000.00"))

    def test_dash_dot_and_case_insensitive_variants(self) -> None:
        # Dashes instead of dots
        price_dash = self.retriever.get_price_by_job_code("AT-01-001")
        self.assertEqual(price_dash, Decimal("250000.00"))

        # Lowercase with extra spaces
        price_lower = self.retriever.get_price_by_job_code("  bt.02.010  ")
        self.assertEqual(price_lower, Decimal("12500"))

        # Mixed case and inconsistent separators
        price_mixed = self.retriever.get_price_by_job_code("Bt-02.010")
        self.assertEqual(price_mixed, Decimal("12500"))

    def test_unknown_code_returns_none(self) -> None:
        self.assertIsNone(self.retriever.get_price_by_job_code("ZZ.99.999"))

    def test_non_string_or_blank_returns_none(self) -> None:
        self.assertIsNone(self.retriever.get_price_by_job_code(None))  # type: ignore[arg-type]
        self.assertIsNone(self.retriever.get_price_by_job_code(12345))  # type: ignore[arg-type]
        self.assertIsNone(self.retriever.get_price_by_job_code("   "))
