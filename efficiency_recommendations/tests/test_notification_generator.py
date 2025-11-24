from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch, MagicMock
from efficiency_recommendations.services.notification_generator import generate_notifications


class NotificationGeneratorTest(TestCase):
    """
    Test suite for notification_generator module.
    
    Uses mocking to:
    - Isolate the function from its dependency (DuplicatePreventionService)
    - Control the behavior of external services
    - Test different scenarios without needing actual database or service calls
    
    WHY USE MOCKS HERE?
    - We're testing notification_generator logic, NOT duplicate prevention
    - DuplicatePreventionService is an external dependency that should be isolated
    - Mocking allows us to control what the service returns to test our function
    - We can test our function's behavior independently
    """

    def setUp(self):
        """Set up test data for all test cases"""
        self.sample_items_with_status = [
            {
                'name': 'Semen Portland',
                'cost': Decimal('50000'),
                'weight_pct': Decimal('10.5'),
                'in_ahsp': True
            },
            {
                'name': 'Cat Tembok Custom',
                'cost': Decimal('75000'),
                'weight_pct': Decimal('5.2'),
                'in_ahsp': False
            },
            {
                'name': 'Batu Bata Merah',
                'cost': Decimal('1000'),
                'weight_pct': Decimal('3.8'),
                'in_ahsp': False
            }
        ]

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_generate_notification_for_item_not_in_ahsp(self, mock_duplicate_service):
        """
        Test notification is generated when item is not in AHSP.
        
        Why mock DuplicatePreventionService?
        - We're testing notification generation logic, not duplicate prevention
        - We want to isolate the function's core behavior
        - We can control what the service returns to test our function
        """
        # Arrange: Mock the remove_duplicates method to return input as-is
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
        items_with_status = [
            {
                'name': 'Keramik Import Khusus',
                'cost': Decimal('80000000'),
                'weight_pct': Decimal('10.60'),
                'in_ahsp': False  # NOT in AHSP
            }
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(len(result), 1)
        notification = result[0]
        self.assertEqual(notification['type'], 'NOT_IN_DATABASE')
        self.assertEqual(notification['item_name'], 'Keramik Import Khusus')
        self.assertIn('tidak ditemukan', notification['message'].lower())
        
        # Verify the mock was called once
        mock_duplicate_service.remove_duplicates.assert_called_once()

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_no_notification_for_item_in_ahsp(self, mock_duplicate_service):
        """
        Test no notification when item IS in AHSP.
        
        Why mock here?
        - Even though no notifications expected, the service is still called
        - We need to mock it to avoid actual service execution
        """
        # Arrange
        mock_duplicate_service.remove_duplicates.return_value = []
        
        items_with_status = [
            {
                'name': 'Pekerjaan Struktur Bangunan',
                'cost': Decimal('500000000'),
                'weight_pct': Decimal('66.23'),
                'in_ahsp': True  # Found in AHSP
            }
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(len(result), 0)
        # Verify service was called with empty list
        mock_duplicate_service.remove_duplicates.assert_called_once_with([])

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_mixed_items_some_in_ahsp_some_not(self, mock_duplicate_service):
        """
        Test notifications for mixed case - some found, some not.
        
        Why mock?
        - We're testing the filtering logic that generates notifications
        - Mock lets us verify correct items are passed to duplicate prevention
        """
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
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

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(len(result), 2)
        notified_items = [n['item_name'] for n in result]
        self.assertIn('Keramik Import Khusus', notified_items)
        self.assertIn('Material Langka XYZ', notified_items)
        self.assertNotIn('Pekerjaan Struktur Bangunan', notified_items)
        self.assertNotIn('Pekerjaan Pondasi', notified_items)
        
        # Verify mock was called
        mock_duplicate_service.remove_duplicates.assert_called_once()

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_all_items_not_in_ahsp(self, mock_duplicate_service):
        """Test when NO items are in AHSP"""
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
        items_with_status = [
            {'name': 'Item A', 'in_ahsp': False},
            {'name': 'Item B', 'in_ahsp': False},
            {'name': 'Item C', 'in_ahsp': False}
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(len(result), 3)

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_all_items_in_ahsp(self, mock_duplicate_service):
        """Test when ALL items are in AHSP"""
        # Arrange
        mock_duplicate_service.remove_duplicates.return_value = []
        
        items_with_status = [
            {'name': 'Item A', 'in_ahsp': True},
            {'name': 'Item B', 'in_ahsp': True},
            {'name': 'Item C', 'in_ahsp': True}
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(len(result), 0)
        mock_duplicate_service.remove_duplicates.assert_called_once_with([])

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_empty_items_list(self, mock_duplicate_service):
        """
        Test with empty items list.
        
        Why mock?
        - We want to ensure the service is NOT called for empty input
        """
        # Act
        result = generate_notifications([])

        # Assert
        self.assertEqual(result, [])
        # Verify the duplicate service was NOT called for empty input
        mock_duplicate_service.remove_duplicates.assert_not_called()

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_notification_message_format(self, mock_duplicate_service):
        """
        Test that notification message is properly formatted.
        
        Why mock?
        - We're testing the message creation logic, not duplicate prevention
        """
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
        items_with_status = [
            {
                'name': 'Keramik Import Khusus',
                'in_ahsp': False
            }
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        message = result[0]['message']
        self.assertIn('Keramik Import Khusus', message)
        self.assertIn('database', message.lower())
        self.assertIn('otomatis', message.lower())

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_notification_has_required_fields(self, mock_duplicate_service):
        """Test that each notification has all required fields"""
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
        items_with_status = [
            {
                'name': 'Test Item',
                'in_ahsp': False
            }
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        notification = result[0]
        self.assertIn('type', notification)
        self.assertIn('item_name', notification)
        self.assertIn('message', notification)

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_notification_type_is_correct(self, mock_duplicate_service):
        """Test that notification type is set correctly"""
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
        items_with_status = [
            {'name': 'Item Not Found', 'in_ahsp': False}
        ]

        # Act
        result = generate_notifications(items_with_status)

        # Assert
        self.assertEqual(result[0]['type'], 'NOT_IN_DATABASE')

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_duplicate_prevention_service_called_with_correct_data(self, mock_duplicate_service):
        """
        Test that we pass the correct data structure to DuplicatePreventionService.
        
        Why mock?
        - We want to verify the integration point without executing the actual service
        - We can inspect what arguments were passed to the mocked service
        """
        # Arrange
        mock_duplicate_service.remove_duplicates.return_value = []
        
        # Act
        generate_notifications(self.sample_items_with_status)

        # Assert: Verify the service was called with correct notification structure
        mock_duplicate_service.remove_duplicates.assert_called_once()
        call_args = mock_duplicate_service.remove_duplicates.call_args[0][0]
        
        # Should have 2 notifications (2 items with in_ahsp=False)
        self.assertEqual(len(call_args), 2)
        
        # Verify notification structure
        for notification in call_args:
            self.assertIn('type', notification)
            self.assertIn('item_name', notification)
            self.assertIn('message', notification)
            self.assertEqual(notification['type'], 'NOT_IN_DATABASE')

    @patch('efficiency_recommendations.services.notification_generator.DuplicatePreventionService')
    def test_preserves_order_of_items(self, mock_duplicate_service):
        """Test that notifications are in same order as input items"""
        # Arrange
        mock_duplicate_service.remove_duplicates.side_effect = lambda x: x
        
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
        """Test that duplicate prevention service removes duplicate notifications"""
        items_with_status = [
            {'name': 'Same Item', 'in_ahsp': False},
            {'name': 'Same Item', 'in_ahsp': False},  # Duplicate item
            {'name': 'Different Item', 'in_ahsp': False}
        ]

        result = generate_notifications(items_with_status)

        # Should have 2 unique notifications (duplicate prevention removes one "Same Item")
        # This is correct behavior - DuplicatePreventionService removes duplicates
        self.assertEqual(len(result), 2)

        # Check that we have both unique items
        item_names = [n['item_name'] for n in result]
        self.assertIn('Same Item', item_names)
        self.assertIn('Different Item', item_names)
        
        # All should be for items not in AHSP
        for notification in result:
            self.assertEqual(notification['type'], 'NOT_IN_DATABASE')
