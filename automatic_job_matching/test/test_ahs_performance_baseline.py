# automatic_job_matching/test/test_ahs_performance_baseline.py
from django.test import TransactionTestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from rencanakan_core.models import Ahs
import time


class AhsRepositoryPerformanceBaseline(TransactionTestCase):
    """BASELINE: Document current performance"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Manually create the table since managed=False prevents auto-creation
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
        # Clean up
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ahs")
        super().tearDownClass()
    
    def test_baseline_by_code_like(self):
        """BASELINE: How many queries does by_code_like use?"""
        repo = DbAhsRepository()
        
        query_counts = []
        times_ms = []
        
        for _ in range(5):
            with CaptureQueriesContext(connection) as ctx:
                start = time.perf_counter()
                repo.by_code_like("AHS.0050")
                elapsed = (time.perf_counter() - start) * 1000
            
            query_counts.append(len(ctx.captured_queries))
            times_ms.append(elapsed)
        
        print(f"\n{'='*60}")
        print(f"BASELINE: by_code_like('AHS.0050')")
        print(f"{'='*60}")
        print(f"Queries: {query_counts[0]} (all runs: {query_counts})")
        print(f"Avg time: {sum(times_ms)/len(times_ms):.2f}ms")
        print(f"Time range: {min(times_ms):.2f} - {max(times_ms):.2f}ms")
        print(f"{'='*60}\n")
        
        # Show actual queries
        with CaptureQueriesContext(connection) as ctx:
            repo.by_code_like("AHS.0050")
        
        print("Query details:")
        for i, query in enumerate(ctx.captured_queries, 1):
            print(f"{i}. {query['sql'][:150]}...")
        print()
    
    def test_baseline_by_name_candidates(self):
        """BASELINE: How fast is by_name_candidates?"""
        repo = DbAhsRepository()
        
        query_counts = []
        times_ms = []
        
        for _ in range(5):
            with CaptureQueriesContext(connection) as ctx:
                start = time.perf_counter()
                repo.by_name_candidates("Material")
                elapsed = (time.perf_counter() - start) * 1000
            
            query_counts.append(len(ctx.captured_queries))
            times_ms.append(elapsed)
        
        print(f"\n{'='*60}")
        print(f"BASELINE: by_name_candidates('Material')")
        print(f"{'='*60}")
        print(f"Queries: {query_counts[0]}")
        print(f"Avg time: {sum(times_ms)/len(times_ms):.2f}ms")
        print(f"Time range: {min(times_ms):.2f} - {max(times_ms):.2f}ms")
        print(f"{'='*60}\n")