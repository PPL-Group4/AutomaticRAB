from decimal import Decimal
from django.test import SimpleTestCase, TestCase, override_settings
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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


class CsvAhspSourceTests(SimpleTestCase):
    def test_csv_source_loads_valid_data(self):
        """Test CSV source loads and parses prices correctly"""
        from automatic_price_matching.price_retrieval import CsvAhspSource

        # Create temp CSV file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("NO;URAIAN;SATUAN;HARGA SATUAN\n")
            f.write("5.1.1.1;Pekerjaan A;unit;Rp 1.250.000,00\n")
            f.write("5.1.1.2;Pekerjaan B;m2;Rp 500.000\n")
            csv_path = Path(f.name)

        try:
            source = CsvAhspSource(csv_path)

            # Test exact code
            price = source.get_price_by_code("5.1.1.1")
            self.assertEqual(price, Decimal("1250000.00"))

            # Test different code
            price2 = source.get_price_by_code("5.1.1.2")
            self.assertEqual(price2, Decimal("500000"))

            # Test unknown code
            self.assertIsNone(source.get_price_by_code("99.99.99"))
        finally:
            csv_path.unlink()

    def test_csv_source_handles_malformed_prices(self):
        """Test CSV source handles invalid price formats"""
        from automatic_price_matching.price_retrieval import CsvAhspSource

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("NO;URAIAN;SATUAN;HARGA SATUAN\n")
            f.write("5.1.1.1;Pekerjaan A;unit;-\n")  # Invalid price
            f.write("5.1.1.2;Pekerjaan B;m2;invalid\n")  # Invalid price
            csv_path = Path(f.name)

        try:
            source = CsvAhspSource(csv_path)

            # Both should return None
            self.assertIsNone(source.get_price_by_code("5.1.1.1"))
            self.assertIsNone(source.get_price_by_code("5.1.1.2"))
        finally:
            csv_path.unlink()

    def test_csv_source_handles_missing_file(self):
        """Test CSV source handles missing file gracefully"""
        from automatic_price_matching.price_retrieval import CsvAhspSource

        source = CsvAhspSource(Path("/nonexistent/path.csv"))

        # Should not crash, just return None
        self.assertIsNone(source.get_price_by_code("5.1.1.1"))

class DatabaseAhspSourceTests(SimpleTestCase):  # ✅ Changed from TestCase
    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_db_source_finds_existing_code(self, mock_ahs):
        """Test DB source retrieves price for existing code"""
        from automatic_price_matching.price_retrieval import DatabaseAhspSource

        # Mock the database query
        mock_obj = Mock()
        mock_obj.unit_price = Decimal("1250000.00")
        mock_obj.code = "5.1.1.1"
        mock_ahs.objects.filter.return_value.first.return_value = mock_obj

        source = DatabaseAhspSource()
        price = source.get_price_by_code("5.1.1.1")

        self.assertEqual(price, Decimal("1250000.00"))
        mock_ahs.objects.filter.assert_called_once()

    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_db_source_case_insensitive_lookup(self, mock_ahs):
        """Test DB source handles case-insensitive lookup"""
        from automatic_price_matching.price_retrieval import DatabaseAhspSource

        mock_obj = Mock()
        mock_obj.unit_price = Decimal("500000")
        mock_obj.code = "AT.01.001"
        mock_ahs.objects.filter.return_value.first.return_value = mock_obj

        source = DatabaseAhspSource()
        price = source.get_price_by_code("at.01.001")

        self.assertEqual(price, Decimal("500000"))

    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_db_source_returns_none_for_missing_code(self, mock_ahs):
        """Test DB source returns None for non-existent code"""
        from automatic_price_matching.price_retrieval import DatabaseAhspSource

        # Mock empty result
        mock_ahs.objects.filter.return_value.first.return_value = None

        source = DatabaseAhspSource()
        result = source.get_price_by_code("ZZ.99.999")

        self.assertIsNone(result)


class CombinedAhspSourceTests(SimpleTestCase):  # ✅ Changed from TestCase
    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_combined_source_prefers_csv_over_db(self, mock_ahs):
        """Test combined source prefers CSV when prices differ"""
        from automatic_price_matching.price_retrieval import CombinedAhspSource, MockAhspSource

        # Mock DB to return one price
        mock_obj = Mock()
        mock_obj.unit_price = Decimal("1000000")
        mock_obj.code = "5.1.1.1"
        mock_ahs.objects.filter.return_value.first.return_value = mock_obj

        # CSV has different price
        csv_mock = MockAhspSource({"5.1.1.1": Decimal("1250000")})

        source = CombinedAhspSource(csv_source=csv_mock)
        price = source.get_price_by_code("5.1.1.1")

        # Should prefer CSV
        self.assertEqual(price, Decimal("1250000"))

    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_combined_source_tries_code_variants(self, mock_ahs):
        """Test combined source tries dash/dot variants"""
        from automatic_price_matching.price_retrieval import CombinedAhspSource

        # Mock DB to return price for "5.1.1.1"
        mock_obj = Mock()
        mock_obj.unit_price = Decimal("1250000")
        mock_obj.code = "5.1.1.1"

        def filter_side_effect(*args, **kwargs):
            mock_result = Mock()
            code_query = kwargs.get('code__iexact') or kwargs.get('code')

            # ✅ Match any variant of "5.1.1.1" or "5-1-1-1"
            if code_query and code_query.replace('-', '.').replace('_', '.').upper() == "5.1.1.1":
                mock_result.first.return_value = mock_obj
            else:
                mock_result.first.return_value = None
            return mock_result

        mock_ahs.objects.filter.side_effect = filter_side_effect

        source = CombinedAhspSource()

        # Query with dashes should still find it
        price = source.get_price_by_code("5-1-1-1")
        self.assertEqual(price, Decimal("1250000"))

    @patch('automatic_price_matching.price_retrieval.Ahs')
    def test_combined_source_falls_back_to_db(self, mock_ahs):
        """Test combined source falls back to DB when CSV fails"""
        from automatic_price_matching.price_retrieval import CombinedAhspSource, CsvAhspSource

        # Mock DB to return price
        mock_obj = Mock()
        mock_obj.unit_price = Decimal("1250000")
        mock_obj.code = "5.1.1.1"
        mock_ahs.objects.filter.return_value.first.return_value = mock_obj

        # CSV has no data (missing file)
        csv_source = CsvAhspSource(Path("/nonexistent/path.csv"))

        source = CombinedAhspSource(csv_source=csv_source)
        price = source.get_price_by_code("5.1.1.1")

        # Should fall back to DB
        self.assertEqual(price, Decimal("1250000"))