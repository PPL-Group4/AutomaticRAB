# automatic_job_matching/utils/benchmark_runner.py
import time
from statistics import mean


class BenchmarkRunner:
    def __init__(self, func, runs=5, warmup=1):
        self.func = func
        self.runs = runs
        self.warmup = warmup

    def run(self):
        # optional warmup (not measured)
        for _ in range(self.warmup):
            self.func()

        times = []
        for _ in range(self.runs):
            start = time.perf_counter()
            self.func()
            end = time.perf_counter()
            times.append((end - start) * 1000.0)  # convert to milliseconds

        return {
            "runs": self.runs,
            "times_ms": times,
            "avg_ms": mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
        }


def run_benchmark(func, repeats=3):
    """Convenience wrapper for quick timing."""
    start = time.perf_counter()
    results = []
    for _ in range(repeats):
        s = time.perf_counter()
        func()
        e = time.perf_counter()
        results.append(e - s)
    end = time.perf_counter()

    total_elapsed = end - start
    return results, total_elapsed
