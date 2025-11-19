from decimal import Decimal
from unittest import TestCase
from efficiency_recommendations.services.notification_generator import generate_notifications


class NotificationGeneratorTest(TestCase):
    """Test generating notifications for items not found in AHSP"""

    def test_generate_notification_for_item_not_in_ahsp(self):
        """Test notification is generated when item is not in AHSP"""
        items_with_status = [
            {
                'name': 'Keramik Import Khusus',
                'cost': Decimal('80000000'),
                'weight_pct': Decimal('10.60'),
                'in_ahsp': False  # NOT in AHSP
            }
        ]

        result = generate_notifications(items_with_status)

        # Should have 1 notification
        self.assertEqual(len(result), 1)

        # Check notification structure
        notification = result[0]
        self.assertEqual(notification['type'], 'NOT_IN_DATABASE')
        self.assertEqual(notification['item_name'], 'Keramik Import Khusus')
        self.assertIn('tidak ditemukan', notification['message'].lower())

    def test_no_notification_for_item_in_ahsp(self):
        """Test no notification when item IS in AHSP"""
        items_with_status = [
            {
                'name': 'Pekerjaan Struktur Bangunan',
                'cost': Decimal('500000000'),
                'weight_pct': Decimal('66.23'),
                'in_ahsp': True  # Found in AHSP
            }
        ]

        result = generate_notifications(items_with_status)

        # Should have NO notifications
        self.assertEqual(len(result), 0)

    def test_mixed_items_some_in_ahsp_some_not(self):
        """Test notifications for mixed case - some found, some not"""
        items_with_status = [
            {
                'name': 'Pekerjaan Struktur Bangunan',
                'in_ahsp': True  # Found
            },
            {
                'name': 'Keramik Import Khusus',
                'in_ahsp': False  # NOT found
            },
            {
                'name': 'Pekerjaan Pondasi',
                'in_ahsp': True  # Found
            },
            {
                'name': 'Material Langka XYZ',
                'in_ahsp': False  # NOT found
            }
        ]

        result = generate_notifications(items_with_status)

        # Should have 2 notifications (for the 2 items not in AHSP)
        self.assertEqual(len(result), 2)

        # Check that notifications are for the correct items
        notified_items = [n['item_name'] for n in result]
        self.assertIn('Keramik Import Khusus', notified_items)
        self.assertIn('Material Langka XYZ', notified_items)
        self.assertNotIn('Pekerjaan Struktur Bangunan', notified_items)
        self.assertNotIn('Pekerjaan Pondasi', notified_items)

    def test_all_items_not_in_ahsp(self):
        """Test when NO items are in AHSP"""
        items_with_status = [
            {'name': 'Item A', 'in_ahsp': False},
            {'name': 'Item B', 'in_ahsp': False},
            {'name': 'Item C', 'in_ahsp': False}
        ]

        result = generate_notifications(items_with_status)

        # Should have 3 notifications
        self.assertEqual(len(result), 3)

    def test_all_items_in_ahsp(self):
        """Test when ALL items are in AHSP"""
        items_with_status = [
            {'name': 'Item A', 'in_ahsp': True},
            {'name': 'Item B', 'in_ahsp': True},
            {'name': 'Item C', 'in_ahsp': True}
        ]

        result = generate_notifications(items_with_status)

        # Should have NO notifications
        self.assertEqual(len(result), 0)

    def test_empty_items_list(self):
        """Test with empty items list"""
        result = generate_notifications([])

        # Should return empty list
        self.assertEqual(result, [])

    def test_notification_message_format(self):
        """Test that notification message is properly formatted"""
        items_with_status = [
            {
                'name': 'Keramik Import Khusus',
                'in_ahsp': False
            }
        ]

        result = generate_notifications(items_with_status)

        message = result[0]['message']

        # Message should include item name
        self.assertIn('Keramik Import Khusus', message)

        # Message should mention database
        self.assertIn('database', message.lower())

        # Message should mention autofill
        self.assertIn('otomatis', message.lower())

    def test_notification_has_required_fields(self):
        """Test that each notification has all required fields"""
        items_with_status = [
            {
                'name': 'Test Item',
                'in_ahsp': False
            }
        ]

        result = generate_notifications(items_with_status)

        notification = result[0]

        # Check required fields exist
        self.assertIn('type', notification)
        self.assertIn('item_name', notification)
        self.assertIn('message', notification)

    def test_notification_type_is_correct(self):
        """Test that notification type is set correctly"""
        items_with_status = [
            {'name': 'Item Not Found', 'in_ahsp': False}
        ]

        result = generate_notifications(items_with_status)

        # Type should be NOT_IN_DATABASE
        self.assertEqual(result[0]['type'], 'NOT_IN_DATABASE')

    def test_preserves_order_of_items(self):
        """Test that notifications are in same order as input items"""
        items_with_status = [
            {'name': 'First Item', 'in_ahsp': False},
            {'name': 'Second Item', 'in_ahsp': False},
            {'name': 'Third Item', 'in_ahsp': False}
        ]

        result = generate_notifications(items_with_status)

        # Check order is preserved
        self.assertEqual(result[0]['item_name'], 'First Item')
        self.assertEqual(result[1]['item_name'], 'Second Item')
        self.assertEqual(result[2]['item_name'], 'Third Item')

    def test_no_duplicate_notifications(self):
        """Test that each item generates only one notification (no duplicates)"""
        items_with_status = [
            {'name': 'Same Item', 'in_ahsp': False},
            {'name': 'Same Item', 'in_ahsp': False},  # Duplicate item
            {'name': 'Different Item', 'in_ahsp': False}
        ]

        result = generate_notifications(items_with_status)

        # The service deduplicates by item name, so we expect 2 unique notifications
        self.assertEqual(len(result), 2)

        # Check that we have notifications for the unique items
        notification_names = [n['item_name'] for n in result]
        self.assertIn('Same Item', notification_names)
        self.assertIn('Different Item', notification_names)

        # All should be for items not in AHSP
        for notification in result:
            self.assertEqual(notification['type'], 'NOT_IN_DATABASE')
