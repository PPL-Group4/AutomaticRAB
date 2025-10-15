from django.test import SimpleTestCase
from unittest.mock import MagicMock
import time

class BenchmarkRunnerTests(SimpleTestCase):
    def test_benchmark_runs_and_reports_metrics(self):
        """
        Expect a BenchmarkRunner that:
        - Accepts a callable and 'runs' count
        - Executes the callable that many times
        - Returns a dict with:
          - runs (int)
          - times_ms (list[float])
          - avg_ms, min_ms, max_ms (float)
        """
        from automatic_job_matching.utils.benchmark_runner import BenchmarkRunner

        fake_work = MagicMock(side_effect=lambda: sum(range(100)))

        runner = BenchmarkRunner(func=fake_work, runs=5, warmup=1)
        result = runner.run()

        # structure validation
        self.assertIsInstance(result, dict)
        for key in ["runs", "times_ms", "avg_ms", "min_ms", "max_ms"]:
            self.assertIn(key, result)

        # logic validation
        self.assertEqual(result["runs"], 5)
        self.assertEqual(len(result["times_ms"]), 5)
        self.assertEqual(fake_work.call_count, 5)

        # metrics sanity
        for t in result["times_ms"]:
            self.assertGreater(t, 0.0)
        self.assertGreaterEqual(result["avg_ms"], result["min_ms"])
        self.assertLessEqual(result["max_ms"], max(result["times_ms"]))


class RunBenchmarkFunctionTests(SimpleTestCase):
    def test_run_benchmark_measures_time_correctly(self):
        """
        Expect run_benchmark() to:
        - execute a callable multiple times
        - return (results, elapsed_time)
        """
        from automatic_job_matching.utils.benchmark_runner import run_benchmark

        def fake_function():
            time.sleep(0.01)
            return "ok"

        results, elapsed = run_benchmark(fake_function, repeats=3)

        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(elapsed, 0.03)  # ≈ 3 × 0.01 seconds
