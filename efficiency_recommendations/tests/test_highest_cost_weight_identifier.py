import unittest
from decimal import Decimal

from efficiency_recommendations.services.highest_cost_weight_identifier import identify_highest_cost_weight_item


class HighestCostWeightIdentifierTest(unittest.TestCase):
    """Test suite for identifying highest cost-weight job items"""

    def setUp(self):
        """Set up test data before each test"""
        # Mock job items with calculated weights
        # Total cost: 755M
        # Structural Work: 500M (66.23%)
        # Foundation: 150M (19.87%)
        # Roofing: 80M (10.60%)
        # Painting: 15M (1.99%)
        # Excavation: 10M (1.32%)
        
        self.job_data = {
            'job_id': 1,
            'job_name': 'Test Project - Building Construction',
            'total_cost': Decimal('755000000.00'),
            'items': [
                {
                    'name': 'Structural Work',
                    'cost': Decimal('500000000.00'),
                    'weight_pct': Decimal('66.23'),
                    'quantity': Decimal('100'),
                    'unit_price': Decimal('5000000')
                },
                {
                    'name': 'Excavation',
                    'cost': Decimal('10000000.00'),
                    'weight_pct': Decimal('1.32'),
                    'quantity': Decimal('200'),
                    'unit_price': Decimal('50000')
                },
                {
                    'name': 'Foundation',
                    'cost': Decimal('150000000.00'),
                    'weight_pct': Decimal('19.87'),
                    'quantity': Decimal('50'),
                    'unit_price': Decimal('3000000')
                },
                {
                    'name': 'Roofing',
                    'cost': Decimal('80000000.00'),
                    'weight_pct': Decimal('10.60'),
                    'quantity': Decimal('80'),
                    'unit_price': Decimal('1000000')
                },
                {
                    'name': 'Painting',
                    'cost': Decimal('15000000.00'),
                    'weight_pct': Decimal('1.99'),
                    'quantity': Decimal('150'),
                    'unit_price': Decimal('100000')
                },
            ]
        }

    def test_identify_highest_cost_weight_item(self):
        """Test identifying the single highest cost-weight item"""
        result = identify_highest_cost_weight_item(self.job_data)
        
        # Check result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['job_id'], 1)
        self.assertEqual(result['job_name'], 'Test Project - Building Construction')
        self.assertEqual(result['total_cost'], Decimal('755000000.00'))
        
        # Check highest item
        highest_item = result['highest_item']
        self.assertIsNotNone(highest_item)
        self.assertEqual(highest_item['name'], "Structural Work")
        self.assertEqual(highest_item['weight_pct'], Decimal('66.23'))
        self.assertEqual(highest_item['cost'], Decimal('500000000.00'))

    def test_highest_item_is_correct(self):
        """Test that the correct item with maximum weight is returned"""
        result = identify_highest_cost_weight_item(self.job_data)
        
        highest_item = result['highest_item']
        
        # Verify this is truly the highest
        for item in self.job_data['items']:
            self.assertLessEqual(item['weight_pct'], highest_item['weight_pct'])

    def test_empty_job_returns_none(self):
        """Test handling of job with no items"""
        empty_job_data = {
            'job_id': 2,
            'job_name': 'Empty Project',
            'total_cost': Decimal('0'),
            'items': []
        }
        result = identify_highest_cost_weight_item(empty_job_data)
        
        self.assertIsNone(result['highest_item'])
        self.assertEqual(result['job_id'], 2)
        self.assertEqual(result['total_cost'], Decimal('0'))

    def test_single_item_job(self):
        """Test job with only one item"""
        single_item_job = {
            'job_id': 3,
            'job_name': 'Single Item Project',
            'total_cost': Decimal('100000.00'),
            'items': [
                {
                    'name': 'Only Item',
                    'cost': Decimal('100000.00'),
                    'weight_pct': Decimal('100.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('100000')
                }
            ]
        }
        result = identify_highest_cost_weight_item(single_item_job)
        
        highest_item = result['highest_item']
        self.assertEqual(highest_item['name'], 'Only Item')
        self.assertEqual(highest_item['weight_pct'], Decimal('100.00'))

    def test_result_includes_all_necessary_fields(self):
        """Test that result includes all necessary fields"""
        result = identify_highest_cost_weight_item(self.job_data)
        
        # Check job-level fields
        self.assertIn('job_id', result)
        self.assertIn('job_name', result)
        self.assertIn('total_cost', result)
        self.assertIn('highest_item', result)
        
        # Check item-level fields
        item = result['highest_item']
        self.assertIn('name', item)
        self.assertIn('cost', item)
        self.assertIn('weight_pct', item)
        self.assertIn('quantity', item)
        self.assertIn('unit_price', item)


if __name__ == '__main__':
    unittest.main()
