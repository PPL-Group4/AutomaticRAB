from django.test import TransactionTestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from rencanakan_core.models import Ahs
import time


class AhsRepositoryOptimizationTests(TransactionTestCase):
    """    
    SLA Requirements:
    - by_code_like: <20ms average
    - by_name_candidates: <20ms average
    - Both: Use exactly 1 query
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create table (same as baseline)
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ahs (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    reference_group_id BIGINT NULL,
                    code VARCHAR(50) NULL,
                    name VARCHAR(500) NULL
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
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ahs")
        super().tearDownClass()
    
    def test_by_code_like_meets_sla(self):
        """
        SLA: by_code_like must complete in <20ms average
        
        Current: ~265ms (FAILS without indexes)
        Target:  <20ms (PASSES with indexes)
        """
        repo = DbAhsRepository()
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            result = repo.by_code_like("AHS.0050")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        print(f"\n{'='*60}")
        print(f"SLA Test: by_code_like")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.2f}ms")
        print(f"Target:  <20.00ms")
        print(f"Status:  {'✅ PASS' if avg_time < 20 else '❌ FAIL'}")
        print(f"{'='*60}\n")
        
        self.assertLess(
            avg_time,
            20.0,
            f"SLA violation: {avg_time:.2f}ms > 20ms. "
            f"Hint: Add index on ahs.code field"
        )
    
    def test_by_name_candidates_meets_sla(self):
        """
        SLA: by_name_candidates must complete in <20ms average
        
        Current: ~258ms (FAILS without indexes)
        Target:  <20ms (PASSES with indexes)
        """
        repo = DbAhsRepository()
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            result = repo.by_name_candidates("Material")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        print(f"\n{'='*60}")
        print(f"SLA Test: by_name_candidates")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.2f}ms")
        print(f"Target:  <20.00ms")
        print(f"Status:  {'✅ PASS' if avg_time < 20 else '❌ FAIL'}")
        print(f"{'='*60}\n")
        
        self.assertLess(
            avg_time,
            20.0,
            f"SLA violation: {avg_time:.2f}ms > 20ms. "
            f"Hint: Add index on ahs.name field"
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