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


