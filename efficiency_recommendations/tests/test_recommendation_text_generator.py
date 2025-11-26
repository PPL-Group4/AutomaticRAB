import unittest
from decimal import Decimal
from efficiency_recommendations.services.recommendation_text_generator import (
    generate_recommendation_text
)


class RecommendationTextGeneratorTest(unittest.TestCase):
    """Test suite for generating recommendation text"""

    def test_generate_text_for_single_highest_item(self):
        """Test generating recommendation text for the highest cost-weight item"""
        highest_item = {
            'name': 'Structural Work',
            'cost': Decimal('500000000.00'),
            'weight_pct': Decimal('66.23'),
            'quantity': Decimal('100'),
            'unit_price': Decimal('5000000')
        }
        
        text = generate_recommendation_text(highest_item)
        
        # Check text contains item name
        self.assertIn("Structural Work", text)
        
        # Check text contains percentage
        self.assertIn("66.23%", text)
        
        # Check text contains recommendation phrase
        self.assertIn("total cost", text.lower())
        self.assertIn("consider", text.lower())
        
    def test_text_format_matches_requirement(self):
        """Test that text format matches PBI requirement example"""
        # Example from PBI: "Structural Work accounts for 42% of the total cost. 
        # Consider evaluating material prices for this job."
        
        highest_item = {
            'name': 'Foundation Work',
            'cost': Decimal('100000.00'),
            'weight_pct': Decimal('33.333333'),
            'quantity': Decimal('10'),
            'unit_price': Decimal('10000')
        }
        
        text = generate_recommendation_text(highest_item)
        
        # Should format to 2 decimal places
        self.assertIn("33.33%", text)
        
    def test_handles_high_percentage(self):
        """Test generating text for item with very high cost weight"""
        highest_item = {
            'name': 'Major Equipment',
            'cost': Decimal('900000000.00'),
            'weight_pct': Decimal('90.00'),
            'quantity': Decimal('1'),
            'unit_price': Decimal('900000000')
        }
        
        text = generate_recommendation_text(highest_item)
        
        self.assertIn("Major Equipment", text)
        self.assertIn("90.00%", text)
        self.assertIsNotNone(text)
        self.assertGreater(len(text), 20)  # Should be a meaningful sentence
        
    def test_handles_low_percentage(self):
        """Test generating text for item with low but highest cost weight"""
        highest_item = {
            'name': 'Minor Work',
            'cost': Decimal('5000000.00'),
            'weight_pct': Decimal('5.25'),
            'quantity': Decimal('100'),
            'unit_price': Decimal('50000')
        }
        
        text = generate_recommendation_text(highest_item)
        
        self.assertIn("Minor Work", text)
        self.assertIn("5.25%", text)
        
    def test_text_is_single_sentence_or_two(self):
        """Test that recommendation is concise (1-2 sentences)"""
        highest_item = {
            'name': 'Test Item',
            'cost': Decimal('100000.00'),
            'weight_pct': Decimal('50.00'),
            'quantity': Decimal('10'),
            'unit_price': Decimal('10000')
        }
        
        text = generate_recommendation_text(highest_item)
        
        # Count sentences by splitting on period followed by space or end
        sentences = [s.strip() for s in text.split('. ') if s.strip()]
        sentence_count = len(sentences)
        self.assertLessEqual(sentence_count, 2, "Text should be concise (max 2 sentences)")
        self.assertGreaterEqual(sentence_count, 1, "Text should have at least 1 sentence")


if __name__ == '__main__':
    unittest.main()
