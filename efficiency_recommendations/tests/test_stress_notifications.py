"""
Stress testing for efficiency_recommendations optimization (PBI-13).

Tests the performance improvement from request-level caching,
ensuring job matching is not redundantly called multiple times.

Test scenarios:
1. Varying dataset sizes (10, 50, 100, 500 items)
2. Concurrent requests
3. Combined workflow (notifications + price deviations)
4. Cache effectiveness
"""
import time
import statistics
import concurrent.futures
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from cost_weight.models import TestJob, TestItem
from decimal import Decimal
from unittest.mock import patch


class StressTestNotificationsEndpoint(TransactionTestCase):
    """Stress test for notifications endpoint with caching optimization."""

    def setUp(self):
        """Set up test jobs with varying item counts."""
        self.job_small = self._create_test_job("Small Job", 10)
        self.job_medium = self._create_test_job("Medium Job", 50)
        self.job_large = self._create_test_job("Large Job", 100)
        self.job_xlarge = self._create_test_job("XL Job", 500)

    def _create_test_job(self, name, item_count):
        """Create a test job with specified number of items."""
        job = TestJob.objects.create(name=name, total_cost=Decimal("0"))

        for i in range(item_count):
            TestItem.objects.create(
                job=job,
                name=f"Test Item {i + 1} - {name}",
                quantity=Decimal("10.00"),
                unit_price=Decimal("1000.00"),
                cost=Decimal("10000.00"),
                weight_pct=Decimal("1.00")
            )

        job.calculate_totals()
        return job

    def _measure_endpoint(self, job_id, endpoint_name):
        """Measure response time for an endpoint."""
        url = reverse(f'efficiency_recommendations:{endpoint_name}', args=[job_id])
        start = time.time()
        response = self.client.get(url)
        duration = time.time() - start
        self.assertEqual(response.status_code, 200)
        return duration

    def test_small_dataset(self):
        """Test with 10 items."""
        duration = self._measure_endpoint(self.job_small.id, 'notifications')
        print(f"\n[10 items] Notifications: {duration:.3f}s")
        self.assertLess(duration, 10.0)

    def test_medium_dataset(self):
        """Test with 50 items."""
        duration = self._measure_endpoint(self.job_medium.id, 'notifications')
        print(f"\n[50 items] Notifications: {duration:.3f}s")
        self.assertLess(duration, 30.0)

    def test_large_dataset(self):
        """Test with 100 items."""
        duration = self._measure_endpoint(self.job_large.id, 'notifications')
        print(f"\n[100 items] Notifications: {duration:.3f}s")
        self.assertLess(duration, 60.0)

    def test_xlarge_dataset(self):
        """Test with 500 items."""
        duration = self._measure_endpoint(self.job_xlarge.id, 'notifications')
        print(f"\n[500 items] Notifications: {duration:.3f}s")
        self.assertLess(duration, 300.0)

    def test_price_deviations_large(self):
        """Test price deviations with 100 items."""
        duration = self._measure_endpoint(self.job_large.id, 'price_deviations')
        print(f"\n[100 items] Price Deviations: {duration:.3f}s")
        self.assertLess(duration, 60.0)

    def test_combined_workflow(self):
        """Test notifications + price deviations together."""
        job_id = self.job_large.id

        notif_url = reverse('efficiency_recommendations:notifications', args=[job_id])
        start = time.time()
        notif_resp = self.client.get(notif_url)
        notif_time = time.time() - start
        self.assertEqual(notif_resp.status_code, 200)

        price_url = reverse('efficiency_recommendations:price_deviations', args=[job_id])
        start = time.time()
        price_resp = self.client.get(price_url)
        price_time = time.time() - start
        self.assertEqual(price_resp.status_code, 200)

        total = notif_time + price_time
        print(f"\n[Combined - 100 items]")
        print(f"  Notifications: {notif_time:.3f}s")
        print(f"  Price Deviations: {price_time:.3f}s")
        print(f"  Total: {total:.3f}s")
        self.assertLess(total, 120.0)

    @patch('efficiency_recommendations.services.matching_cache_service.MatchingService.perform_best_match')
    def test_cache_effectiveness(self, mock_match):
        """Verify caching reduces matching calls."""
        mock_match.return_value = {
            'code': 'TEST-001',
            'unit_price': 1000.0,
            'confidence': 0.95
        }

        job_id = self.job_medium.id
        item_count = self.job_medium.items.count()

        # Call notifications
        notif_url = reverse('efficiency_recommendations:notifications', args=[job_id])
        self.client.get(notif_url)
        notif_calls = mock_match.call_count

        # Reset and call price deviations
        mock_match.reset_mock()
        price_url = reverse('efficiency_recommendations:price_deviations', args=[job_id])
        self.client.get(price_url)
        price_calls = mock_match.call_count

        print(f"\n[Cache Test - 50 items]")
        print(f"  Notifications calls: {notif_calls}")
        print(f"  Price Deviations calls: {price_calls}")
        print(f"  Expected: ~{item_count} per endpoint")

        # Should call matching once per item, not multiple times
        self.assertLessEqual(notif_calls, item_count + 5)
        self.assertLessEqual(price_calls, item_count + 5)


class StressConcurrentRequests(TransactionTestCase):
    """Stress test for concurrent requests."""

    def setUp(self):
        """Create test jobs for concurrency testing."""
        self.jobs = [
            self._create_test_job(f"Job {i}", 50)
            for i in range(5)
        ]

    def _create_test_job(self, name, item_count):
        """Create test job."""
        job = TestJob.objects.create(name=name, total_cost=Decimal("0"))
        for i in range(item_count):
            TestItem.objects.create(
                job=job,
                name=f"Item {i + 1} - {name}",
                quantity=Decimal("5.00"),
                unit_price=Decimal("500.00"),
                cost=Decimal("2500.00"),
                weight_pct=Decimal("1.00")
            )
        job.calculate_totals()
        return job

    def _fetch_notifications(self, job_id):
        """Fetch notifications for a job."""
        from django.test import Client
        client = Client()
        url = reverse('efficiency_recommendations:notifications', args=[job_id])
        start = time.time()
        response = client.get(url)
        return {
            'job_id': job_id,
            'status': response.status_code,
            'duration': time.time() - start
        }

    def test_concurrent_requests(self):
        """Test 5 concurrent requests."""
        job_ids = [job.id for job in self.jobs]
        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._fetch_notifications, jid) for jid in job_ids]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        total = time.time() - start

        for r in results:
            self.assertEqual(r['status'], 200)

        durations = [r['duration'] for r in results]
        avg = statistics.mean(durations)
        max_dur = max(durations)

        print(f"\n[Concurrent - 5 jobs × 50 items]")
        print(f"  Total: {total:.3f}s")
        print(f"  Average: {avg:.3f}s")
        print(f"  Max: {max_dur:.3f}s")

        # Concurrent should be faster than sequential
        self.assertLess(total, avg * 5)


class StressDataAccuracy(TransactionTestCase):
    """Verify data accuracy under stress."""

    def setUp(self):
        """Create job for accuracy testing."""
        self.job = TestJob.objects.create(name="Accuracy Job", total_cost=Decimal("0"))
        for i in range(100):
            TestItem.objects.create(
                job=self.job,
                name=f"Item {i + 1}",
                quantity=Decimal("10.00"),
                unit_price=Decimal("1000.00"),
                cost=Decimal("10000.00"),
                weight_pct=Decimal("1.00")
            )
        self.job.calculate_totals()

    def test_notifications_accuracy(self):
        """Verify notifications returns accurate data."""
        url = reverse('efficiency_recommendations:notifications', args=[self.job.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('job_id', data)
        self.assertIn('total_items', data)
        self.assertIn('notifications', data)
        self.assertEqual(data['job_id'], self.job.id)
        self.assertEqual(data['total_items'], 100)

        print(f"\n[Accuracy]")
        print(f"  Job: {data['job_id']}")
        print(f"  Items: {data['total_items']}")
        print(f"  Notifications: {data['items_not_in_ahsp']}")

    def test_price_deviations_accuracy(self):
        """Verify price deviations returns accurate data."""
        url = reverse('efficiency_recommendations:price_deviations', args=[self.job.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('job_id', data)
        self.assertIn('total_items', data)
        self.assertIn('deviations', data)
        self.assertEqual(data['job_id'], self.job.id)
        self.assertEqual(data['total_items'], 100)

        print(f"\n[Price Accuracy]")
        print(f"  Job: {data['job_id']}")
        print(f"  Items: {data['total_items']}")
        print(f"  Checked: {data['items_checked']}")
        print(f"  Deviations: {data['deviations_found']}")
