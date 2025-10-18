from django.test import TransactionTestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from rencanakan_core.models import Ahs
import time
import logging


class AhsRepositoryOptimizationTests(TransactionTestCase):
    """    
    SLA Requirements:
    - by_code_like: <100ms average
    - by_name_candidates: <100ms average
    - Both: Use exactly 1 query
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.disable(logging.CRITICAL)

        # Create table (same as baseline)
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ahs (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                reference_group_id BIGINT NULL,
                code VARCHAR(50) NULL,
                name VARCHAR(500) NULL,
                INDEX idx_ahs_code (code),
                INDEX idx_ahs_name (name(255))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        
        # Insert test data
        for i in range(100):
            Ahs.objects.create(
                code=f"AHS.{i:04d}",
                name=f"Material Type {i % 10}"
            )
    
    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)  # Re-enable

        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ahs")
        super().tearDownClass()
    
    def test_by_code_like_meets_sla(self):
        """
        SLA: by_code_like must complete in <100ms average
        """
        repo = DbAhsRepository()
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            repo.by_code_like("AHS.0050")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        print(f"\n{'='*60}")
        print("SLA Test: by_code_like")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.2f}ms")
        print("Target:  <100.00ms")
        print(f"Status:  {'✅ PASS' if avg_time < 100 else '❌ FAIL'}")
        print(f"{'='*60}\n")
        
        self.assertLess(
            avg_time,
            100.0,
            f"SLA violation: {avg_time:.2f}ms > 100ms. "
            f"Hint: Add index on ahs.code field"
        )
    
    def test_by_name_candidates_meets_sla(self):
        """
        SLA: by_name_candidates must complete in <100ms average
        """
        repo = DbAhsRepository()
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            repo.by_name_candidates("Material")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        print(f"\n{'='*60}")
        print("SLA Test: by_name_candidates")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.2f}ms")
        print("Target:  <100.00ms")
        print(f"Status:  {'✅ PASS' if avg_time < 100 else '❌ FAIL'}")
        print(f"{'='*60}\n")
        
        self.assertLess(
            avg_time,
            100.0,
            f"SLA violation: {avg_time:.2f}ms > 100ms. "
        )
    
    def test_query_count_sla(self):
        """
        SLA: Each method must use exactly 1 database query
        """
        repo = DbAhsRepository()
        
        # Test by_code_like
        with CaptureQueriesContext(connection) as ctx:
            repo.by_code_like("AHS.0050")
        
        self.assertEqual(
            len(ctx.captured_queries),
            1,
            f"by_code_like used {len(ctx.captured_queries)} queries, expected 1"
        )
        
        # Test by_name_candidates
        with CaptureQueriesContext(connection) as ctx:
            repo.by_name_candidates("Material")
        
        self.assertEqual(
            len(ctx.captured_queries),
            1,
            f"by_name_candidates used {len(ctx.captured_queries)} queries, expected 1"
        )