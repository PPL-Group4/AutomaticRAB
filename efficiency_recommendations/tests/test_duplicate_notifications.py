from decimal import Decimal
from unittest import TestCase
from efficiency_recommendations.services.notification_generator import generate_notifications
from efficiency_recommendations.services.duplicate_prevention_service import DuplicatePreventionService


class DuplicateNotificationPreventionTest(TestCase):
    
    def test_duplicate_prevention_service_removes_duplicates(self):
        """Test that the DuplicatePreventionService correctly removes duplicates"""
        notifications = [
            {'type': 'NOT_IN_DATABASE', 'message': 'Item X not found'},
            {'type': 'NOT_IN_DATABASE', 'message': 'Item X not found'},
            {'type': 'NOT_IN_DATABASE', 'message': 'Item Y not found'},
        ]
        
        unique = DuplicatePreventionService.remove_duplicates(notifications)
        
        self.assertEqual(len(unique), 2)
        self.assertFalse(DuplicatePreventionService.has_duplicates(unique))
    
    def test_duplicate_prevention_service_detects_duplicates(self):
        """Test that the service can detect if duplicates exist"""
        notifications_with_dupes = [
            {'type': 'warning', 'message': 'Item X not found'},
            {'type': 'warning', 'message': 'Item X not found'},
        ]
        
        notifications_without_dupes = [
            {'type': 'warning', 'message': 'Item X not found'},
            {'type': 'warning', 'message': 'Item Y not found'},
        ]
        
        self.assertTrue(DuplicatePreventionService.has_duplicates(notifications_with_dupes))
        self.assertFalse(DuplicatePreventionService.has_duplicates(notifications_without_dupes))
    
    def test_duplicate_prevention_service_counts_duplicates(self):
        """Test that the service can count duplicate entries"""
        notifications = [
            {'type': 'warning', 'message': 'Item X not found'},
            {'type': 'warning', 'message': 'Item X not found'},
            {'type': 'warning', 'message': 'Item Y not found'},
            {'type': 'warning', 'message': 'Item Y not found'},
            {'type': 'info', 'message': 'Item Z found'},
        ]
        
        count = DuplicatePreventionService.get_duplicate_count(notifications)
        self.assertEqual(count, 2)  # X and Y are duplicated

    def test_no_duplicate_notifications_for_same_item(self):
        """Test that duplicate items only generate one notification"""
        items_with_status = [
            {'name': 'Keramik Import Khusus', 'in_ahsp': False},
            {'name': 'Pekerjaan Pondasi', 'in_ahsp': True},
            {'name': 'Keramik Import Khusus', 'in_ahsp': False},  # Duplicate
        ]

        result = generate_notifications(items_with_status)

        # Should only have 1 notification for the duplicate item
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_name'], 'Keramik Import Khusus')

    def test_no_duplicate_notifications_multiple_duplicates(self):
        """Test handling multiple duplicate items"""
        items_with_status = [
            {'name': 'Item A', 'in_ahsp': False},
            {'name': 'Item B', 'in_ahsp': False},
            {'name': 'Item A', 'in_ahsp': False},  # Duplicate
            {'name': 'Item C', 'in_ahsp': True},
            {'name': 'Item B', 'in_ahsp': False},  # Duplicate
            {'name': 'Item A', 'in_ahsp': False},  # Duplicate again
        ]

        result = generate_notifications(items_with_status)

        # Should only have 2 notifications (Item A and Item B)
        self.assertEqual(len(result), 2)
        
        notified_items = [n['item_name'] for n in result]
        self.assertIn('Item A', notified_items)
        self.assertIn('Item B', notified_items)
        self.assertNotIn('Item C', notified_items)
        
        # Each item should appear only once
        self.assertEqual(notified_items.count('Item A'), 1)
        self.assertEqual(notified_items.count('Item B'), 1)

    def test_duplicate_items_preserves_first_occurrence(self):
        """Test that when duplicates exist, the first occurrence is preserved"""
        items_with_status = [
            {'name': 'Duplicate Item', 'in_ahsp': False, 'cost': Decimal('1000')},
            {'name': 'Other Item', 'in_ahsp': True},
            {'name': 'Duplicate Item', 'in_ahsp': False, 'cost': Decimal('2000')},
        ]

        result = generate_notifications(items_with_status)

        # Should have 1 notification
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_name'], 'Duplicate Item')

    def test_case_sensitive_duplicate_detection(self):
        """Test that duplicate detection is case-sensitive"""
        items_with_status = [
            {'name': 'Keramik Import', 'in_ahsp': False},
            {'name': 'keramik import', 'in_ahsp': False},  # Different case
            {'name': 'KERAMIK IMPORT', 'in_ahsp': False},  # Different case
        ]

        result = generate_notifications(items_with_status)

        # Should have 3 notifications (case-sensitive means these are different)
        self.assertEqual(len(result), 3)

    def test_no_duplicates_with_all_unique_items(self):
        """Test that unique items all generate notifications"""
        items_with_status = [
            {'name': 'Item 1', 'in_ahsp': False},
            {'name': 'Item 2', 'in_ahsp': False},
            {'name': 'Item 3', 'in_ahsp': False},
        ]

        result = generate_notifications(items_with_status)

        # Should have 3 notifications
        self.assertEqual(len(result), 3)

    def test_many_duplicates_of_same_item(self):
        """Test handling many duplicates of the same item"""
        items_with_status = [
            {'name': 'Repeated Item', 'in_ahsp': False},
            {'name': 'Repeated Item', 'in_ahsp': False},
            {'name': 'Repeated Item', 'in_ahsp': False},
            {'name': 'Repeated Item', 'in_ahsp': False},
            {'name': 'Repeated Item', 'in_ahsp': False},
        ]

        result = generate_notifications(items_with_status)

        # Should only have 1 notification despite 5 occurrences
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_name'], 'Repeated Item')
