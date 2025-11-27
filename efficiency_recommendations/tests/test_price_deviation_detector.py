import unittest
from decimal import Decimal

from efficiency_recommendations.services.price_deviation_detector import DeviationLevel, PriceDeviationDetector


class TestPriceDeviationDetector(unittest.TestCase):
    """Test suite for PriceDeviationDetector service"""

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