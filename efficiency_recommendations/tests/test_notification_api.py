from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from cost_weight.models import TestJob, TestItem
from unittest.mock import patch
import json


class NotificationAPITest(TestCase):
    """TDD tests for notification display API endpoint"""

    def setUp(self):
        """Set up test data before each test"""
        self.client = Client()

        # Create a test job
        self.job = TestJob.objects.create(
            name="Test Construction Project",
            total_cost=Decimal('630000000')
        )

        # Create test items (no in_ahsp field in database)
        self.item1 = TestItem.objects.create(
            name="Pekerjaan Struktur Bangunan",
            job=self.job,
            quantity=Decimal('1'),
            unit_price=Decimal('500000000'),
            weight_pct=Decimal('79.37')
        )

        self.item2 = TestItem.objects.create(
            name="Keramik Import Khusus",
            job=self.job,
            quantity=Decimal('1'),
            unit_price=Decimal('80000000'),
            weight_pct=Decimal('12.70')
        )

        self.item3 = TestItem.objects.create(
            name="Material Langka XYZ",
            job=self.job,
            quantity=Decimal('1'),
            unit_price=Decimal('50000000'),
            weight_pct=Decimal('7.94')
        )

    def test_api_returns_json_response(self):
        """Test that API returns JSON response with correct structure"""
        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': self.job.id}
        )

        with patch(
            'efficiency_recommendations.views.check_items_in_ahsp'
        ) as mock_check:
            # Mock: all items found in AHSP
            mock_check.return_value = [
                {'name': 'Pekerjaan Struktur', 'cost': Decimal('500000000'),
                 'weight_pct': Decimal('79.37'), 'in_ahsp': True},
            ]

            response = self.client.get(url)

        # Check response is JSON
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        # Check response structure
        data = json.loads(response.content)
        self.assertIn('job_id', data)
        self.assertIn('total_items', data)
        self.assertIn('items_not_in_ahsp', data)
        self.assertIn('notifications', data)

    @patch('efficiency_recommendations.views.check_items_in_ahsp')
    def test_api_returns_notifications_for_items_not_in_ahsp(self, mock_check):
        """Test API generates notifications for items NOT found in AHSP"""

        # Mock: 2 items NOT in AHSP, 1 item IN AHSP
        mock_check.return_value = [
            {
                'name': 'Pekerjaan Struktur Bangunan',
                'cost': Decimal('500000000'),
                'weight_pct': Decimal('79.37'),
                'in_ahsp': True  # Found in AHSP
            },
            {
                'name': 'Keramik Import Khusus',
                'cost': Decimal('80000000'),
                'weight_pct': Decimal('12.70'),
                'in_ahsp': False  # NOT in AHSP
            },
            {
                'name': 'Material Langka XYZ',
                'cost': Decimal('50000000'),
                'weight_pct': Decimal('7.94'),
                'in_ahsp': False  # NOT in AHSP
            }
        ]

        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': self.job.id}
        )
        response = self.client.get(url)

        data = json.loads(response.content)

        # Should have 2 notifications (for items not in AHSP)
        self.assertEqual(data['total_items'], 3)
        self.assertEqual(data['items_not_in_ahsp'], 2)
        self.assertEqual(len(data['notifications']), 2)

        # Check notification structure
        notification = data['notifications'][0]
        self.assertEqual(notification['type'], 'NOT_IN_DATABASE')
        self.assertIn('item_name', notification)
        self.assertIn('message', notification)
        self.assertIn(
            'tidak ditemukan',
            notification['message'].lower()
        )

    @patch('efficiency_recommendations.views.check_items_in_ahsp')
    def test_api_returns_empty_notifications_when_all_items_in_ahsp(
        self, mock_check
    ):
        """Test API returns empty notifications when all items are in AHSP"""

        # Mock: All items found in AHSP
        mock_check.return_value = [
            {'name': 'Item 1', 'cost': Decimal('500000000'),
             'weight_pct': Decimal('79.37'), 'in_ahsp': True},
            {'name': 'Item 2', 'cost': Decimal('80000000'),
             'weight_pct': Decimal('12.70'), 'in_ahsp': True},
            {'name': 'Item 3', 'cost': Decimal('50000000'),
             'weight_pct': Decimal('7.94'), 'in_ahsp': True},
        ]

        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': self.job.id}
        )
        response = self.client.get(url)

        data = json.loads(response.content)

        # Should have NO notifications
        self.assertEqual(data['total_items'], 3)
        self.assertEqual(data['items_not_in_ahsp'], 0)
        self.assertEqual(len(data['notifications']), 0)

    def test_api_returns_404_for_nonexistent_job(self):
        """Test API returns 404 for non-existent job ID"""
        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': 99999}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_api_handles_job_with_no_items(self):
        """Test API handles job with no items"""
        # Create empty job
        empty_job = TestJob.objects.create(
            name="Empty Project",
            total_cost=Decimal('0')
        )

        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': empty_job.id}
        )
        response = self.client.get(url)

        data = json.loads(response.content)

        # Should return empty notifications
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['total_items'], 0)
        self.assertEqual(data['items_not_in_ahsp'], 0)
        self.assertEqual(len(data['notifications']), 0)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed"""
        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': self.job.id}
        )

        # POST should not be allowed
        response = self.client.post(url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

        # PUT should not be allowed
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)

        # DELETE should not be allowed
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)

        # GET should be allowed
        with patch(
            'efficiency_recommendations.views.check_items_in_ahsp'
        ) as mock:
            mock.return_value = []
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    @patch('efficiency_recommendations.views.check_items_in_ahsp')
    def test_api_calls_ahsp_checker_with_correct_data(self, mock_check):
        """Test that API calls AHSP checker with correct item data"""

        mock_check.return_value = []

        url = reverse(
            'efficiency_recommendations:notifications',
            kwargs={'job_id': self.job.id}
        )
        self.client.get(url)

        # Verify AHSP checker was called
        mock_check.assert_called_once()

        # Verify it was called with correct structure
        called_items = mock_check.call_args[0][0]
        self.assertEqual(len(called_items), 3)  # 3 items in setUp

        # Verify items have correct fields
        first_item = called_items[0]
        self.assertIn('name', first_item)
        self.assertIn('cost', first_item)
        self.assertIn('weight_pct', first_item)
