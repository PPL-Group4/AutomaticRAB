from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch, MagicMock
from efficiency_recommendations.services.ahsp_availability_checker import check_items_in_ahsp


class AhspAvailabilityCheckerTest(TestCase):
    """Test checking if items exist in AHSP database"""

    def setUp(self):
        """Set up test data"""
        self.items = [
            {
                'name': 'Pekerjaan Struktur Bangunan',
                'cost': Decimal('500000000'),
                'weight_pct': Decimal('66.23'),
                'quantity': Decimal('1'),
                'unit_price': Decimal('500000000')
            },
            {
                'name': 'Pekerjaan Pondasi',
                'cost': Decimal('150000000'),
                'weight_pct': Decimal('19.87'),
                'quantity': Decimal('1'),
                'unit_price': Decimal('150000000')
            },
            {
                'name': 'Keramik Import Khusus Tier 1',
                'cost': Decimal('80000000'),
                'weight_pct': Decimal('10.60'),
                'quantity': Decimal('1'),
                'unit_price': Decimal('80000000')
            }
        ]

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_all_items_found_in_ahsp(self, mock_matching_service):
        """Test when all items are found in AHSP database"""
        # Mock: all items return a match
        mock_matching_service.perform_best_match.side_effect = [
            {'name': 'Pekerjaan Struktur Bangunan', 'code': 'A001'},
            {'name': 'Pekerjaan Pondasi', 'code': 'A002'},
            {'name': 'Keramik Import Khusus Tier 1', 'code': 'A003'}
        ]

        result = check_items_in_ahsp(self.items)

        # All items should be marked as found
        self.assertEqual(len(result), 3)
        self.assertTrue(result[0]['in_ahsp'])
        self.assertTrue(result[1]['in_ahsp'])
        self.assertTrue(result[2]['in_ahsp'])

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_some_items_not_found_in_ahsp(self, mock_matching_service):
        """Test when some items are NOT found in AHSP database"""
        # Mock: first two found, third NOT found (returns None)
        mock_matching_service.perform_best_match.side_effect = [
            {'name': 'Pekerjaan Struktur Bangunan', 'code': 'A001'},
            {'name': 'Pekerjaan Pondasi', 'code': 'A002'},
            None  # Third item not found
        ]

        result = check_items_in_ahsp(self.items)

        # First two should be found
        self.assertTrue(result[0]['in_ahsp'])
        self.assertEqual(result[0]['name'], 'Pekerjaan Struktur Bangunan')

        self.assertTrue(result[1]['in_ahsp'])
        self.assertEqual(result[1]['name'], 'Pekerjaan Pondasi')

        # Third should NOT be found
        self.assertFalse(result[2]['in_ahsp'])
        self.assertEqual(result[2]['name'], 'Keramik Import Khusus Tier 1')

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_no_items_found_in_ahsp(self, mock_matching_service):
        """Test when NO items are found in AHSP database"""
        # Mock: all return None
        mock_matching_service.perform_best_match.return_value = None

        result = check_items_in_ahsp(self.items)

        # All items should be marked as NOT found
        self.assertEqual(len(result), 3)
        for item_result in result:
            self.assertFalse(item_result['in_ahsp'])

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_result_preserves_original_item_data(self, mock_matching_service):
        """Test that result includes original item information"""
        mock_matching_service.perform_best_match.return_value = {
            'name': 'Pekerjaan Struktur Bangunan',
            'code': 'A001'
        }

        result = check_items_in_ahsp([self.items[0]])

        # Should preserve original item data
        self.assertEqual(result[0]['name'], 'Pekerjaan Struktur Bangunan')
        self.assertEqual(result[0]['weight_pct'], Decimal('66.23'))
        self.assertEqual(result[0]['cost'], Decimal('500000000'))
        self.assertEqual(result[0]['quantity'], Decimal('1'))
        self.assertEqual(result[0]['unit_price'], Decimal('500000000'))

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_empty_items_list_returns_empty(self, mock_matching_service):
        """Test with empty items list"""
        result = check_items_in_ahsp([])

        # Should return empty list
        self.assertEqual(result, [])
        # Should not call matching service
        mock_matching_service.perform_best_match.assert_not_called()

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_handles_matching_service_exception(self, mock_matching_service):
        """Test graceful handling when matching service throws exception"""
        # Mock: matching service throws exception
        mock_matching_service.perform_best_match.side_effect = Exception("Database connection error")

        result = check_items_in_ahsp([self.items[0]])

        # Should mark item as not found when exception occurs
        self.assertFalse(result[0]['in_ahsp'])

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_handles_empty_match_result_list(self, mock_matching_service):
        """Test when matching service returns empty list instead of None"""
        # Some matching services return [] for no match instead of None
        mock_matching_service.perform_best_match.return_value = []

        result = check_items_in_ahsp([self.items[0]])

        # Empty list should also be treated as "not found"
        self.assertFalse(result[0]['in_ahsp'])

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_result_structure_has_required_fields(self, mock_matching_service):
        """Test that result has correct structure with all required fields"""
        mock_matching_service.perform_best_match.return_value = {
            'name': 'Pekerjaan Struktur Bangunan',
            'code': 'A001'
        }

        result = check_items_in_ahsp([self.items[0]])

        # Check required fields exist
        required_fields = ['name', 'cost', 'weight_pct', 'in_ahsp']
        for field in required_fields:
            self.assertIn(field, result[0], f"Missing required field: {field}")

    @patch('efficiency_recommendations.services.ahsp_availability_checker.MatchingService')
    def test_matching_service_called_with_item_name(self, mock_matching_service):
        """Test that matching service is called with the correct item name"""
        mock_matching_service.perform_best_match.return_value = {'name': 'Match', 'code': 'A001'}

        check_items_in_ahsp([self.items[0]])

        # Verify matching service was called with item name
        mock_matching_service.perform_best_match.assert_called_once_with('Pekerjaan Struktur Bangunan')
