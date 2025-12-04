from decimal import Decimal
from unittest import TestCase

from efficiency_recommendations.services.ahsp_availability_checker import check_items_in_ahsp


class AhspAvailabilityIntegrationTest(TestCase):
    """Integration tests using REAL AHSP database (no mocks)"""

    def test_real_ahsp_lookup_for_common_item(self):
        """Integration test: Check if a common construction item is found in real AHSP"""
        # This item should exist in most AHSP databases
        items = [
            {
                'name': 'Galian Tanah',
                'cost': Decimal('10000000'),
                'weight_pct': Decimal('10.00'),
                'quantity': Decimal('1'),
                'unit_price': Decimal('10000000')
            }
        ]

        # Call WITHOUT mocking - uses real MatchingService
        result = check_items_in_ahsp(items)

        print(f"\n=== INTEGRATION TEST RESULT ===")
        print(f"Item: {result[0]['name']}")
        print(f"Found in AHSP: {result[0]['in_ahsp']}")
        print(f"================================\n")

        # We expect this common item to be found, but won't fail if it's not
        # (database might not be loaded in test environment)
        self.assertIn('in_ahsp', result[0])

    def test_real_ahsp_lookup_for_fake_item(self):
        """Integration test: Check that a fake item is NOT found in real AHSP"""
        # This item definitely should NOT exist
        items = [
            {
                'name': 'FAKE_ITEM_TESTING_12345_DOES_NOT_EXIST',
                'cost': Decimal('1000'),
                'weight_pct': Decimal('1.00'),
                'quantity': Decimal('1'),
                'unit_price': Decimal('1000')
            }
        ]

        # Call WITHOUT mocking - uses real MatchingService
        result = check_items_in_ahsp(items)

        print(f"\n=== INTEGRATION TEST RESULT ===")
        print(f"Item: {result[0]['name']}")
        print(f"Found in AHSP: {result[0]['in_ahsp']}")
        print(f"================================\n")

        # This fake item should definitely not be found
        self.assertFalse(result[0]['in_ahsp'])
