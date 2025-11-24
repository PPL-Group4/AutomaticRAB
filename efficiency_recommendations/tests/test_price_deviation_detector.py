import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from efficiency_recommendations.services.price_deviation_detector import (
    PriceDeviationDetector,
    DeviationLevel
)


class TestPriceDeviationDetector(unittest.TestCase):
    """
    Test suite for PriceDeviationDetector service.
    
    Uses mocking to:
    - Test internal methods independently
    - Isolate the calculation logic from formatting logic
    - Verify method interactions
    
    WHY USE MOCKS HERE?
    - To test complex methods in isolation
    - To verify that helper methods are called correctly
    - To control the output of private methods for testing public methods
    """

    def setUp(self):
        """Set up test fixtures before each test"""
        self.detector = PriceDeviationDetector()

    def test_no_deviation_within_threshold(self):
        """Test that items within threshold show no deviation"""
        # Reference price: 100,000
        # Actual price: 105,000 (5% increase - within default 10% threshold)
        items = [{
            'name': 'Pasir',
            'actual_price': Decimal('105000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 0, "Should not detect deviation within threshold"

    def test_deviation_above_threshold_positive(self):
        """Test detection of price increase above threshold"""
        # Reference price: 100,000
        # Actual price: 125,000 (25% increase - above 10% threshold)
        items = [{
            'name': 'Semen',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 1
        assert result[0]['item_name'] == 'Semen'
        assert result[0]['type'] == 'PRICE_DEVIATION'
        assert result[0]['deviation_percentage'] == Decimal('25.0')
        assert result[0]['deviation_level'] == DeviationLevel.HIGH

    def test_deviation_above_threshold_negative(self):
        """Test detection of price decrease above threshold"""
        # Reference price: 100,000
        # Actual price: 75,000 (25% decrease - above 10% threshold)
        items = [{
            'name': 'Bata',
            'actual_price': Decimal('75000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 1
        assert result[0]['item_name'] == 'Bata'
        assert result[0]['deviation_percentage'] == Decimal('-25.0')
        assert result[0]['deviation_level'] == DeviationLevel.HIGH

    def test_custom_threshold(self):
        """Test using custom deviation threshold"""
        detector = PriceDeviationDetector(threshold_percentage=5.0)
        
        # 7% deviation should be detected with 5% threshold
        items = [{
            'name': 'Keramik',
            'actual_price': Decimal('107000'),
            'reference_price': Decimal('100000')
        }]

        result = detector.detect_deviations(items)

        assert len(result) == 1
        assert result[0]['deviation_percentage'] == Decimal('7.0')

    def test_threshold_boundary_exact(self):
        """Test exact threshold boundary (should NOT trigger)"""
        detector = PriceDeviationDetector(threshold_percentage=10.0)
        
        # Exactly 10% deviation - should NOT be detected
        items = [{
            'name': 'Cat',
            'actual_price': Decimal('110000'),
            'reference_price': Decimal('100000')
        }]

        result = detector.detect_deviations(items)

        assert len(result) == 0, "Exact threshold should not trigger deviation"

    def test_threshold_boundary_just_above(self):
        """Test just above threshold boundary (should trigger)"""
        detector = PriceDeviationDetector(threshold_percentage=10.0)
        
        # 10.1% deviation - should be detected
        items = [{
            'name': 'Cat',
            'actual_price': Decimal('110100'),
            'reference_price': Decimal('100000')
        }]

        result = detector.detect_deviations(items)

        assert len(result) == 1

    def test_moderate_deviation_level(self):
        """Test moderate deviation level (10-20%)"""
        items = [{
            'name': 'Item A',
            'actual_price': Decimal('115000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert result[0]['deviation_level'] == DeviationLevel.MODERATE

    def test_high_deviation_level(self):
        """Test high deviation level (20-50%)"""
        items = [{
            'name': 'Item B',
            'actual_price': Decimal('135000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert result[0]['deviation_level'] == DeviationLevel.HIGH

    def test_critical_deviation_level(self):
        """Test critical deviation level (>50%)"""
        items = [{
            'name': 'Item C',
            'actual_price': Decimal('200000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert result[0]['deviation_level'] == DeviationLevel.CRITICAL

    def test_multiple_items_mixed(self):
        """Test detection with multiple items, some with deviations"""
        items = [
            {
                'name': 'Item OK',
                'actual_price': Decimal('105000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Item Deviated',
                'actual_price': Decimal('130000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Item Also OK',
                'actual_price': Decimal('98000'),
                'reference_price': Decimal('100000')
            }
        ]

        result = self.detector.detect_deviations(items)

        assert len(result) == 1
        assert result[0]['item_name'] == 'Item Deviated'

    def test_multiple_deviations(self):
        """Test detection with multiple items having deviations"""
        items = [
            {
                'name': 'High Price',
                'actual_price': Decimal('150000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Low Price',
                'actual_price': Decimal('50000'),
                'reference_price': Decimal('100000')
            }
        ]

        result = self.detector.detect_deviations(items)

        assert len(result) == 2
        item_names = [r['item_name'] for r in result]
        assert 'High Price' in item_names
        assert 'Low Price' in item_names

    def test_empty_items_list(self):
        """Test with empty items list"""
        result = self.detector.detect_deviations([])
        assert result == []

    def test_missing_reference_price(self):
        """Test item without reference price (skip detection)"""
        items = [{
            'name': 'No Reference',
            'actual_price': Decimal('125000'),
            'reference_price': None
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 0

    def test_zero_reference_price(self):
        """Test item with zero reference price (skip to avoid division by zero)"""
        items = [{
            'name': 'Zero Reference',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('0')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 0

    def test_missing_actual_price(self):
        """Test item without actual price (skip detection)"""
        items = [{
            'name': 'No Actual Price',
            'actual_price': None,
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 0

    def test_message_contains_item_name(self):
        """Test that message contains item name"""
        items = [{
            'name': 'Semen Portland',
            'actual_price': Decimal('150000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        message = result[0]['message']
        assert 'Semen Portland' in message

    def test_message_not_empty(self):
        """Test that message is generated and not empty"""
        items = [{
            'name': 'Bata Merah',
            'actual_price': Decimal('60000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        message = result[0]['message']
        assert message is not None
        assert len(message) > 0

    # MESSAGE FORMATTING TESTS

    def test_message_includes_deviation_percentage(self):
        """Test that message includes deviation percentage"""
        items = [{
            'name': 'Semen',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should include percentage (25.0% or +25.0%)
        assert '25.0%' in message or '+25.0%' in message

    def test_message_includes_actual_price(self):
        """Test that message includes actual price with currency format"""
        items = [{
            'name': 'Bata',
            'actual_price': Decimal('150000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should include formatted actual price
        assert 'Rp 150,000' in message or 'Rp150,000' in message or '150000' in message

    def test_message_includes_reference_price(self):
        """Test that message includes reference price with currency format"""
        items = [{
            'name': 'Cat',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should include formatted reference price
        assert 'Rp 100,000' in message or 'Rp100,000' in message or '100000' in message

    def test_message_format_for_price_increase(self):
        """Test message format shows price increase clearly"""
        items = [{
            'name': 'Keramik',
            'actual_price': Decimal('130000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should indicate increase with + sign or "higher"/"naik"
        has_increase_indicator = (
            '+30.0%' in message or 
            'higher' in message.lower() or 
            'naik' in message.lower() or
            'lebih tinggi' in message.lower()
        )
        assert has_increase_indicator, f"Message should indicate price increase: {message}"

    def test_message_format_for_price_decrease(self):
        """Test message format shows price decrease clearly"""
        items = [{
            'name': 'Paku',
            'actual_price': Decimal('70000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should indicate decrease with - sign or "lower"/"turun"
        has_decrease_indicator = (
            '-30.0%' in message or 
            'lower' in message.lower() or 
            'turun' in message.lower() or
            'lebih rendah' in message.lower()
        )
        assert has_decrease_indicator, f"Message should indicate price decrease: {message}"

    def test_message_price_formatting_with_thousands_separator(self):
        """Test that prices are formatted with thousands separator"""
        items = [{
            'name': 'Material Mahal',
            'actual_price': Decimal('1500000'),
            'reference_price': Decimal('1000000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Should have comma/dot separators for readability
        has_separator = '1,500,000' in message or '1.500.000' in message
        assert has_separator, f"Prices should be formatted with separators: {message}"

    def test_message_readable_structure(self):
        """Test that message has readable structure with all components"""
        items = [{
            'name': 'Besi Beton',
            'actual_price': Decimal('180000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)
        message = result[0]['message']

        # Message should contain all key components
        assert 'Besi Beton' in message  # Item name
        assert '80.0%' in message or '+80.0%' in message  # Percentage
        # At least one price should be visible
        has_price = 'Rp' in message or '180000' in message or '100000' in message
        assert has_price, f"Message should include price information: {message}"

    def test_message_format_consistency_multiple_items(self):
        """Test that all messages follow consistent format"""
        items = [
            {
                'name': 'Item A',
                'actual_price': Decimal('120000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Item B',
                'actual_price': Decimal('80000'),
                'reference_price': Decimal('100000')
            }
        ]

        result = self.detector.detect_deviations(items)

        # Both messages should have similar structure
        msg1 = result[0]['message']
        msg2 = result[1]['message']

        # Check both have percentages
        assert '%' in msg1 and '%' in msg2
        # Check both have item names
        assert 'Item' in msg1 and 'Item' in msg2

    def test_percentage_calculation_precision(self):
        """Test precise percentage calculation"""
        items = [{
            'name': 'Item',
            'actual_price': Decimal('123456'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        # (123456 - 100000) / 100000 * 100 = 23.456%
        assert result[0]['deviation_percentage'] == Decimal('23.456')

    def test_rounding_precision(self):
        """Test that deviation percentage is rounded to reasonable precision"""
        items = [{
            'name': 'Item',
            'actual_price': Decimal('115555'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        # Should be rounded to 1-3 decimal places
        deviation = result[0]['deviation_percentage']
        assert abs(deviation - Decimal('15.555')) < Decimal('0.001')

    def test_result_structure_complete(self):
        """Test that result contains all required fields"""
        items = [{
            'name': 'Complete Test',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('100000')
        }]

        result = self.detector.detect_deviations(items)

        assert len(result) == 1
        deviation = result[0]
        
        # Check all required fields
        assert 'type' in deviation
        assert 'item_name' in deviation
        assert 'message' in deviation
        assert 'deviation_percentage' in deviation
        assert 'deviation_level' in deviation
        assert 'actual_price' in deviation
        assert 'reference_price' in deviation

    def test_sort_by_deviation_magnitude(self):
        """Test that results are sorted by deviation magnitude (highest first)"""
        items = [
            {
                'name': 'Small Dev',
                'actual_price': Decimal('112000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Large Dev',
                'actual_price': Decimal('180000'),
                'reference_price': Decimal('100000')
            },
            {
                'name': 'Medium Dev',
                'actual_price': Decimal('140000'),
                'reference_price': Decimal('100000')
            }
        ]

        result = self.detector.detect_deviations(items)

        assert len(result) == 3
        # Should be sorted by absolute deviation: 80%, 40%, 12%
        assert result[0]['item_name'] == 'Large Dev'
        assert result[1]['item_name'] == 'Medium Dev'
        assert result[2]['item_name'] == 'Small Dev'

    def test_ignore_non_positive_reference_price(self):
        """SCRUM-119: Items with non-positive reference_price are ignored."""
        items = [
            {'name': 'Neg Ref', 'actual_price': Decimal('120000'), 'reference_price': Decimal('-100000')},  # nonsensical
            {'name': 'Zero Ref', 'actual_price': Decimal('120000'), 'reference_price': Decimal('0')},       # already covered
            {'name': 'OK', 'actual_price': Decimal('120000'), 'reference_price': Decimal('100000')},
        ]
        result = self.detector.detect_deviations(items)
        # Only the valid one should be considered -> 20% deviation
        assert len(result) == 1
        assert result[0]['item_name'] == 'OK'
        assert result[0]['deviation_percentage'] == Decimal('20.0')


    def test_ignore_missing_reference_price_key(self):
        items = [
            {'name': 'Missing Ref', 'actual_price': Decimal('120000')},  # no reference_price key
            {'name': 'Valid', 'actual_price': Decimal('130000'), 'reference_price': Decimal('100000')},
        ]
        result = self.detector.detect_deviations(items)
        assert len(result) == 1
        assert result[0]['item_name'] == 'Valid'

    # MOCK-BASED TESTS FOR SCORE 2
    
    @patch.object(PriceDeviationDetector, '_generate_message')
    def test_message_generation_called_for_deviations(self, mock_generate_message):
        """
        Test that _generate_message is called for items with deviations.
        
        Why mock _generate_message?
        - We want to test that the detect_deviations method correctly
          identifies items and calls the message generator
        - We isolate the detection logic from the message formatting logic
        """
        # Arrange
        mock_generate_message.return_value = "Mocked message"
        
        items = [{
            'name': 'Semen',
            'actual_price': Decimal('125000'),
            'reference_price': Decimal('100000')
        }]

        # Act
        result = self.detector.detect_deviations(items)

        # Assert
        # Should call _generate_message once for the one deviation
        assert mock_generate_message.call_count == 1
        assert len(result) == 1
        assert result[0]['message'] == "Mocked message"

    @patch.object(PriceDeviationDetector, '_get_deviation_level')
    def test_deviation_level_assigned_correctly(self, mock_get_level):
        """
        Test that deviation level is correctly assigned.
        
        Why mock _get_deviation_level?
        - We want to verify it's called with the correct deviation value
        - We can control the returned level to test the flow
        """
        # Arrange
        mock_get_level.return_value = DeviationLevel.CRITICAL
        
        items = [{
            'name': 'Item X',
            'actual_price': Decimal('200000'),
            'reference_price': Decimal('100000')
        }]

        # Act
        result = self.detector.detect_deviations(items)

        # Assert
        # Verify the method was called
        assert mock_get_level.call_count == 1
        # Verify the returned level is used
        assert result[0]['deviation_level'] == DeviationLevel.CRITICAL

    @patch.object(PriceDeviationDetector, '_check_single_item')
    def test_detect_deviations_processes_all_items(self, mock_check_item):
        """
        Test that detect_deviations processes each item.
        
        Why mock _check_single_item?
        - We want to verify the main method calls the checker for each item
        - We isolate the iteration logic from the checking logic
        """
        # Arrange
        mock_check_item.side_effect = [
            {'item_name': 'Item 1', 'deviation_percentage': Decimal('15.0')},
            None,  # Second item has no deviation
            {'item_name': 'Item 3', 'deviation_percentage': Decimal('25.0')}
        ]
        
        items = [
            {'name': 'Item 1', 'actual_price': Decimal('115000'), 'reference_price': Decimal('100000')},
            {'name': 'Item 2', 'actual_price': Decimal('105000'), 'reference_price': Decimal('100000')},
            {'name': 'Item 3', 'actual_price': Decimal('125000'), 'reference_price': Decimal('100000')}
        ]

        # Act
        result = self.detector.detect_deviations(items)

        # Assert
        # Should call _check_single_item for each item
        assert mock_check_item.call_count == 3
        # Should only return items with deviations (not None)
        assert len(result) == 2
        assert result[0]['item_name'] == 'Item 3'  # Sorted by deviation
        assert result[1]['item_name'] == 'Item 1'

    @patch.object(PriceDeviationDetector, '_calculate_deviation_percentage')
    def test_calculation_method_called(self, mock_calculate):
        """
        Test that deviation calculation method is invoked.
        
        Why mock _calculate_deviation_percentage?
        - We verify the calculation is performed
        - We can inject specific deviation values to test thresholds
        """
        # Arrange
        mock_calculate.return_value = Decimal('15.5')
        
        items = [{
            'name': 'Test Item',
            'actual_price': Decimal('115500'),
            'reference_price': Decimal('100000')
        }]

        # Act
        result = self.detector.detect_deviations(items)

        # Assert
        # Verify calculation was called with correct prices
        mock_calculate.assert_called_once_with(
            Decimal('115500'),
            Decimal('100000')
        )
        # Verify the calculated deviation is used
        assert result[0]['deviation_percentage'] == Decimal('15.5')

    @patch.object(PriceDeviationDetector, '_format_price')
    def test_price_formatting_called(self, mock_format_price):
        """
        Test that price formatting is used in message generation.
        
        Why mock _format_price?
        - We verify prices are formatted before including in messages
        - We can control the format to test message construction
        """
        # Arrange
        mock_format_price.side_effect = lambda x: f"{int(x):,}"
        
        items = [{
            'name': 'Keramik',
            'actual_price': Decimal('150000'),
            'reference_price': Decimal('100000')
        }]

        # Act
        result = self.detector.detect_deviations(items)

        # Assert
        # Should call format_price twice (actual and reference)
        assert mock_format_price.call_count == 2
        # Verify prices were passed to formatter
        calls = [call[0][0] for call in mock_format_price.call_args_list]
        assert Decimal('150000') in calls
        assert Decimal('100000') in calls
